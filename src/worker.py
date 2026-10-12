"""
Модуль воркера.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config, Task
from .db import DatabaseManager
from .parser import CSVProcessor
from .schemas.models import get_schema_for_file

logger = logging.getLogger(__name__)


def process_task(task: Task, db: DatabaseManager, config: Config) -> int:
    """Обрабатывает одну задачу: читает CSV и загружает данные в PostgreSQL."""
    file_path = Path(task.file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    schema_class = get_schema_for_file(file_path.name)
    if schema_class is None:
        raise ValueError(f"Неподдерживаемый тип файла: {file_path.name}")

    processor = CSVProcessor(file_path, config.batch_size, schema_class)
    processor.prepare()

    table_name = processor.table_name
    total_rows = 0

    with db.get_connection() as conn:
        # Создаём таблицу если нужно
        db.create_data_table(conn, table_name, processor.all_columns[:-4])

        # КРИТИЧНО: Очищаем старые данные этого файла перед вставкой.
        # Это гарантирует идемпотентность — при повторной обработке
        # (после сбоя) не будет дублей.
        deleted = db.cleanup_file_data(conn, table_name, task.file_path)
        if deleted > 0:
            logger.info(
                "Задача %d: очищено %d старых строк для файла %s.",
                task.id,
                deleted,
                file_path.name,
            )

        # Потоковая вставка батчами
        for batch in processor.read_batches(
            month=task.month,
            date=task.date,
            time=task.time,
            file_path_str=task.file_path,
        ):
            db.insert_batch_copy(
                conn=conn,
                table_name=table_name,
                all_columns=processor.all_columns,
                rows=batch,
            )
            conn.commit()
            total_rows += len(batch)
            logger.debug(
                "Задача %d: вставлено %d строк в таблицу %s.",
                task.id,
                total_rows,
                table_name,
            )

    if processor.validation_errors_count > 0:
        logger.warning(
            "Файл %s: %d строк пропущено из-за ошибок валидации",
            file_path.name,
            processor.validation_errors_count,
        )

    return total_rows