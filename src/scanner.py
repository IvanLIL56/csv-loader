"""
Модуль сканирования директорий.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from .config import Config, Task
from .db import DatabaseManager
from .filters.file_filter import FileFilter

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def parse_date_folder(folder_name: str) -> str | None:
    """Преобразует название папки даты (ДД.ММ.ГГГГ) в ISO-формат."""
    match = _DATE_PATTERN.match(folder_name)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        dt = datetime(int(year), int(month), int(day), tzinfo=UTC)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        logger.warning("Некорректная дата в имени папки: %s", folder_name)
        return None


def extract_metadata(file_path: Path, root_dir: Path) -> Task | None:
    """Извлекает метаданные из пути к CSV-файлу."""
    try:
        rel_path = file_path.relative_to(root_dir)
    except ValueError:
        logger.warning("Файл вне корневой директории: %s", file_path)
        return None

    parts = rel_path.parts
    if len(parts) != 4:
        logger.debug(
            "Файл %s пропущен: ожидалось 4 уровня, получено %d. Путь: %s",
            file_path.name,
            len(parts),
            rel_path,
        )
        return None

    month_folder = parts[0]
    date_folder = parts[1]
    time_folder = parts[2]
    filename = parts[3]

    if not filename.lower().endswith(".csv"):
        logger.debug("Файл %s пропущен: не CSV файл", filename)
        return None

    iso_date = parse_date_folder(date_folder)
    if iso_date is None:
        logger.warning(
            "Файл %s пропущен: некорректная дата в папке '%s'",
            filename,
            date_folder,
        )
        return None

    return Task(
        file_path=str(file_path),
        month=month_folder,
        date=iso_date,
        time=time_folder,
    )


def scan_directory(config: Config, db: DatabaseManager) -> int:
    """Рекурсивно обходит директорию и добавляет задачи в очередь."""
    logger.info("Начало сканирования директории: %s", config.root_dir)

    file_filter = FileFilter()
    logger.info("Разрешённые файлы: %s", file_filter.allowed_filenames)

    new_tasks: list[Task] = []

    all_csv_files = list(config.root_dir.rglob("*.csv"))
    logger.info("Найдено всего CSV файлов: %d", len(all_csv_files))

    filtered_files = file_filter.filter_files(all_csv_files)

    for file_path in filtered_files:
        task = extract_metadata(file_path, config.root_dir)
        if task is not None:
            new_tasks.append(task)
        else:
            logger.debug("Файл пропущен (не соответствует структуре): %s", file_path)

    logger.info(
        "Обработано файлов: %d, распознано задач: %d.",
        len(filtered_files),
        len(new_tasks),
    )

    if new_tasks:
        db.insert_tasks_batch(new_tasks)

    return len(new_tasks)