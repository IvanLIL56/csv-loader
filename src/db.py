"""
Модуль работы с базой данных PostgreSQL.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import psycopg2
import psycopg2.extensions
import psycopg2.pool

from .config import Config, Task

logger = logging.getLogger(__name__)

DATA_SCHEMA = "sbx_t_sva"


class DatabaseManager:
    """Инкапсулирует все операции с PostgreSQL."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None

    def initialize_pool(self) -> None:
        """Создаёт пул соединений."""
        max_conn = self._config.workers + 3
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=max_conn,
            dsn=self._config.db_url,
        )
        logger.info("Пул соединений инициализирован (макс. соединений: %d).", max_conn)

    def close_pool(self) -> None:
        """Закрывает пул соединений."""
        if self._pool is not None:
            self._pool.closeall()
            logger.info("Пул соединений закрыт.")

    @contextmanager
    def get_connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Контекстный менеджер: выдаёт соединение из пула."""
        if self._pool is None:
            raise RuntimeError("Пул соединений не инициализирован.")
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def ensure_schema_exists(self) -> None:
        """Проверяет существование схемы и создаёт её если нужно."""
        sql = f"CREATE SCHEMA IF NOT EXISTS {DATA_SCHEMA};"
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        logger.info("Схема %s проверена/создана.", DATA_SCHEMA)

    def create_tasks_table(self) -> None:
        """Создаёт таблицу задач в схеме sbx_t_sva."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        CREATE TABLE IF NOT EXISTS {full_table_name} (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            month TEXT NOT NULL,
            date DATE NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        logger.info("Таблица задач проверена/создана: %s", full_table_name)

    def insert_tasks_batch(self, tasks: Sequence[Task]) -> int:
        """Пакетная вставка новых задач."""
        if not tasks:
            return 0

        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        INSERT INTO {full_table_name} (file_path, month, date, time, status)
        VALUES (%s, %s, %s, %s, 'pending')
        ON CONFLICT (file_path) DO NOTHING
        """
        values = [(t.file_path, t.month, t.date, t.time) for t in tasks]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, values)
            conn.commit()

        count = self._count_tasks_by_status("pending")
        logger.info(
            "В очередь добавлено задач: %d (всего pending: %d).",
            len(tasks),
            count,
        )
        return len(tasks)

    def _count_tasks_by_status(self, status: str) -> int:
        """Возвращает количество задач с указанным статусом."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {full_table_name} WHERE status = %s",
                    (status,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def fetch_task(self) -> Task | None:
        """Атомарно забирает одну задачу из очереди."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        WITH selected AS (
            SELECT id FROM {full_table_name}
            WHERE status = 'pending'
            ORDER BY id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE {full_table_name}
        SET status = 'processing', updated_at = NOW()
        FROM selected
        WHERE {full_table_name}.id = selected.id
        RETURNING {full_table_name}.id, {full_table_name}.file_path,
                  {full_table_name}.month, {full_table_name}.date::text,
                  {full_table_name}.time
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
            conn.commit()

            if row is None:
                return None

            return Task(
                id=row[0],
                file_path=row[1],
                month=row[2],
                date=row[3],
                time=row[4],
                status="processing",
            )

    def update_task_done(self, task_id: int, rows_inserted: int) -> None:
        """Помечает задачу как выполненную."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        UPDATE {full_table_name}
        SET status = 'done', updated_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (task_id,))
            conn.commit()
        logger.debug("Задача %d завершена (строк: %d).", task_id, rows_inserted)

    def update_task_error(self, task_id: int, error_message: str) -> None:
        """Помечает задачу как ошибочную."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        UPDATE {full_table_name}
        SET status = 'error', error_message = %s, updated_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (error_message, task_id))
            conn.commit()
        logger.warning("Задача %d помечена как ошибка: %s", task_id, error_message)

    def reset_stuck_tasks(self, timeout_seconds: int) -> int:
        """Сбрасывает зависшие задачи обратно в 'pending'."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        UPDATE {full_table_name}
        SET status = 'pending', updated_at = NOW(), error_message = NULL
        WHERE status = 'processing'
          AND updated_at < %s
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (cutoff,))
                count = cur.rowcount
            conn.commit()
        if count > 0:
            logger.info("Сброшено зависших задач: %d.", count)
        return count

    def has_active_tasks(self) -> bool:
        """Проверяет, есть ли ещё активные задачи."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        sql = f"""
        SELECT COUNT(*) FROM {full_table_name}
        WHERE status IN ('pending', 'processing')
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return (row[0] if row else 0) > 0

    def get_total_tasks_count(self) -> int:
        """Возвращает общее количество задач."""
        full_table_name = f"{DATA_SCHEMA}.tasks"
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {full_table_name}")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    @staticmethod
    def quote_identifier(name: str) -> str:
        """Экранирует идентификатор PostgreSQL двойными кавычками."""
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    def table_exists(
        self, conn: psycopg2.extensions.connection, table_name: str
    ) -> bool:
        """Проверяет, существует ли таблица в схеме sbx_t_sva."""
        sql = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        )
        """
        with conn.cursor() as cur:
            cur.execute(sql, (DATA_SCHEMA, table_name))
            row = cur.fetchone()
            return bool(row[0]) if row else False

    def get_table_columns(
        self, conn: psycopg2.extensions.connection, table_name: str
    ) -> set[str]:
        """Возвращает множество имён колонок существующей таблицы."""
        sql = """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (DATA_SCHEMA, table_name))
            rows = cur.fetchall()
            return {row[0] for row in rows}

    def create_data_table(
        self,
        conn: psycopg2.extensions.connection,
        table_name: str,
        csv_columns: list[str],
    ) -> None:
        """Создаёт целевую таблицу для данных из CSV в схеме sbx_t_sva."""
        full_table_name = f"{DATA_SCHEMA}.{self.quote_identifier(table_name)}"

        col_defs: list[str] = []
        for col in csv_columns:
            col_defs.append(f"    {self.quote_identifier(col)} TEXT")

        col_defs.append(f'    {self.quote_identifier("_month")} TEXT')
        col_defs.append(f'    {self.quote_identifier("_date")} DATE')
        col_defs.append(f'    {self.quote_identifier("_time")} TEXT')
        col_defs.append(f'    {self.quote_identifier("_file_path")} TEXT')

        columns_sql = ",\n".join(col_defs)
        sql = f"CREATE TABLE IF NOT EXISTS {full_table_name} (\n{columns_sql}\n);"

        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        logger.info(
            "Создана таблица: %s (колонок: %d).",
            full_table_name,
            len(csv_columns) + 4,
        )

    def cleanup_file_data(
        self,
        conn: psycopg2.extensions.connection,
        table_name: str,
        file_path: str,
    ) -> int:
        """
        Удаляет все строки, связанные с указанным файлом.

        Это обеспечивает идемпотентность: при повторной обработке файла
        старые данные удаляются и заменяются новыми.

        Returns:
            Количество удалённых строк.
        """
        full_table_name = f"{DATA_SCHEMA}.{self.quote_identifier(table_name)}"
        sql = f"""
        DELETE FROM {full_table_name}
        WHERE "_file_path" = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (file_path,))
            deleted_count = cur.rowcount
        conn.commit()
        if deleted_count > 0:
            logger.info(
                "Удалено %d строк из %s для файла %s (очистка перед вставкой).",
                deleted_count,
                full_table_name,
                file_path,
            )
        return deleted_count

    def insert_batch_copy(
        self,
        conn: psycopg2.extensions.connection,
        table_name: str,
        all_columns: list[str],
        rows: list[list[str]],
    ) -> None:
        """Вставляет батч строк через COPY в схему sbx_t_sva."""
        if not rows:
            return

        full_table_name = f"{DATA_SCHEMA}.{self.quote_identifier(table_name)}"
        quoted_cols = ", ".join(self.quote_identifier(c) for c in all_columns)

        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)
        buffer.seek(0)

        copy_sql = (
            f"COPY {full_table_name} ({quoted_cols}) "
            f"FROM STDIN WITH (FORMAT csv, HEADER false)"
        )

        with conn.cursor() as cur:
            cur.execute("SET LOCAL synchronous_commit = off;")
            cur.copy_expert(copy_sql, buffer)