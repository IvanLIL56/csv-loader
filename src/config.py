"""
Модуль конфигурации.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / "pars_settings.env")


class Task(BaseModel):
    """Модель задачи на загрузку одного CSV-файла."""

    id: int | None = None
    file_path: str
    month: str
    date: str
    time: str
    status: str = "pending"
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExecutionStats(BaseModel):
    """Агрегированная статистика выполнения программы."""

    total_files: int = 0
    processed: int = 0
    errors: int = 0
    skipped: int = 0
    total_rows_inserted: int = 0
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None


class Config(BaseModel):
    """Основная конфигурация приложения."""

    root_dir: Path
    db_url: str
    workers: int = 4
    batch_size: int = 1000
    log_level: str = "INFO"
    stuck_timeout_seconds: int = 3600
    file_pattern: str = "*.csv"

    @field_validator("root_dir", mode="before")
    @classmethod
    def validate_root_dir(cls, v: str | Path) -> Path:
        """Валидирует и нормализует путь к корневой директории."""
        path = Path(v).resolve()
        if not path.is_dir():
            raise ValueError(f"Корневая директория не существует: {path}")
        return path

    @field_validator("db_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        """Проверяет, что строка подключения не пустая."""
        if not v or not v.strip():
            raise ValueError("DATABASE_URL не может быть пустым")
        return v.strip()


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Загрузка CSV-файлов в PostgreSQL с очередью задач."
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default=os.environ.get("ROOT_DIR", ""),
        help="Корневая директория с CSV-файлами.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.environ.get("DATABASE_URL", ""),
        help="Строка подключения к PostgreSQL.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("WORKERS", "4")),
        help="Количество потоков-воркеров.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("BATCH_SIZE", "1000")),
        help="Размер батча для вставки строк.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Уровень логирования.",
    )
    parser.add_argument(
        "--file-pattern",
        type=str,
        default=os.environ.get("FILE_PATTERN", "*.csv"),
        help="Паттерн для фильтрации файлов.",
    )
    return parser.parse_args()


def load_config() -> Config:
    """Загружает конфигурацию из .env файла и аргументов CLI."""
    args = parse_args()

    if not args.root_dir:
        raise ValueError(
            "Необходимо указать --root-dir или установить переменную ROOT_DIR."
        )

    if not args.db_url:
        raise ValueError(
            "Необходимо указать --db-url или установить переменную DATABASE_URL."
        )

    return Config(
        root_dir=args.root_dir,
        db_url=args.db_url,
        workers=args.workers,
        batch_size=args.batch_size,
        log_level=args.log_level,
        file_pattern=args.file_pattern,
    )


def setup_logging(level_str: str) -> None:
    """Настраивает базовое логирование."""
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )