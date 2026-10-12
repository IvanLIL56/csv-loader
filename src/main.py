"""
Главный модуль — точка входа программы.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Config, ExecutionStats, load_config
from .db import DatabaseManager
from .logging_config import setup_logging
from .scanner import scan_directory
from .worker import process_task

logger = logging.getLogger(__name__)

_shutdown_event = threading.Event()


def _signal_handler(signum: int, frame: Any) -> None:
    """Обработчик сигналов завершения."""
    logger.info("Получен сигнал %d. Завершаем работу...", signum)
    _shutdown_event.set()


def _worker_loop(
    worker_id: int,
    db: DatabaseManager,
    config: Config,
    stats: ExecutionStats,
    stats_lock: threading.Lock,
) -> None:
    """Основной цикл воркера."""
    thread_name = f"Worker-{worker_id}"
    logger.info("%s запущен.", thread_name)

    while not _shutdown_event.is_set():
        task = db.fetch_task()

        if task is None:
            if not db.has_active_tasks():
                logger.info("%s: активных задач нет. Завершаю.", thread_name)
                break
            _shutdown_event.wait(timeout=2.0)
            continue

        try:
            rows = process_task(task, db, config)
            if task.id is not None:
                task_id: int = task.id
                db.update_task_done(task_id, rows)

            with stats_lock:
                stats.processed += 1
                stats.total_rows_inserted += rows

            logger.info(
                "%s: файл %s обработан (строк: %d).",
                thread_name,
                Path(task.file_path).name,
                rows,
            )
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "%s: ошибка при обработке %s: %s",
                thread_name,
                Path(task.file_path).name,
                error_msg,
            )
            if task.id is not None:
                task_id_err: int = task.id
                try:
                    db.update_task_error(task_id_err, error_msg)
                except Exception as db_exc:
                    logger.error("Не удалось обновить статус задачи в БД: %s", db_exc)

            with stats_lock:
                stats.errors += 1

    logger.info("%s завершил работу.", thread_name)


def _monitor_loop(
    stats: ExecutionStats,
    stats_lock: threading.Lock,
    total_tasks: int,
    interval: float = 15.0,
) -> None:
    """Периодически выводит статистику выполнения в лог."""
    while not _shutdown_event.is_set():
        _shutdown_event.wait(timeout=interval)
        if _shutdown_event.is_set():
            break

        with stats_lock:
            done = stats.processed
            errors = stats.errors
            rows = stats.total_rows_inserted

        elapsed = (datetime.now(UTC) - stats.start_time).total_seconds()
        speed = done / elapsed if elapsed > 0 else 0.0
        pct = (done + errors) / total_tasks * 100 if total_tasks > 0 else 0.0

        logger.info(
            "Прогресс: %d/%d (%.1f%%) | Обработано: %d | Ошибок: %d | "
            "Строк: %d | Скорость: %.1f файл/сек | Прошло: %.0f сек",
            done + errors,
            total_tasks,
            pct,
            done,
            errors,
            rows,
            speed,
            elapsed,
        )


def run(config: Config) -> ExecutionStats:
    """Основная функция запуска."""
    stats = ExecutionStats()
    stats_lock = threading.Lock()

    db = DatabaseManager(config)
    try:
        db.initialize_pool()
        db.ensure_schema_exists()
        db.create_tasks_table()

        scan_directory(config, db)

        total_tasks = db.get_total_tasks_count()
        stats.total_files = total_tasks
        logger.info("Всего задач в очереди: %d.", total_tasks)

        if total_tasks == 0:
            logger.info("Нет задач для обработки. Завершение.")
            stats.end_time = datetime.now(UTC)
            return stats

        db.reset_stuck_tasks(config.stuck_timeout_seconds)

        total_tasks = db.get_total_tasks_count()
        stats.total_files = total_tasks

        monitor_thread = threading.Thread(
            target=_monitor_loop,
            args=(stats, stats_lock, total_tasks),
            daemon=True,
        )
        monitor_thread.start()

        logger.info("Запуск %d воркеров...", config.workers)
        futures: list[Future[None]] = []

        with ThreadPoolExecutor(max_workers=config.workers) as executor:
            for i in range(config.workers):
                future = executor.submit(
                    _worker_loop, i, db, config, stats, stats_lock
                )
                futures.append(future)

            for future in futures:
                future.result()

        stats.end_time = datetime.now(UTC)
        logger.info("Все воркеры завершили работу.")

    finally:
        db.close_pool()

    return stats


def main() -> None:
    """Точка входа программы."""
    try:
        config = load_config()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)

    log_file = setup_logging(config.log_level)

    logger.info(
        "Конфигурация загружена: root=%s, workers=%d, batch=%d",
        config.root_dir,
        config.workers,
        config.batch_size,
    )

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    stats = run(config)

    elapsed = (stats.end_time - stats.start_time).total_seconds() if stats.end_time else 0
    logger.info("=" * 60)
    logger.info("ИТОГО:")
    logger.info("  Всего файлов:    %d", stats.total_files)
    logger.info("  Обработано:      %d", stats.processed)
    logger.info("  Ошибок:          %d", stats.errors)
    logger.info("  Строк вставлено: %d", stats.total_rows_inserted)
    logger.info("  Время работы:    %.1f сек", elapsed)
    logger.info("  Лог-файл:        %s", log_file)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()