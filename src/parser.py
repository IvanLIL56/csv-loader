"""
Модуль парсинга CSV-файлов с валидацией.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schemas.models import BaseCSVSchema

logger = logging.getLogger(__name__)

METADATA_COLUMNS: list[str] = ["_month", "_date", "_time", "_file_path"]


def detect_encoding(file_path: Path) -> str:
    """Определяет кодировку CSV-файла."""
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            with open(file_path, encoding=encoding) as f:
                f.read(8192)
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue

    logger.warning(
        "Не удалось определить кодировку для %s, используется utf-8.",
        file_path,
    )
    return "utf-8"


class CSVProcessor:
    """Потоковый процессор CSV-файла с валидацией."""

    def __init__(
        self,
        file_path: Path,
        batch_size: int,
        schema_class: type[BaseCSVSchema],
    ) -> None:
        self._file_path = file_path
        self._batch_size = batch_size
        self._schema_class = schema_class
        self._encoding: str | None = None
        self._raw_columns: list[str] = []
        self._column_indices: dict[str, int] = {}
        self._validation_errors: int = 0

    @property
    def table_name(self) -> str:
        """Возвращает имя таблицы для этого типа файла."""
        return self._schema_class.get_table_name()

    @property
    def all_columns(self) -> list[str]:
        """Полный список колонок для вставки."""
        return self._schema_class.get_column_names() + METADATA_COLUMNS

    @property
    def validation_errors_count(self) -> int:
        """Возвращает количество ошибок валидации."""
        return self._validation_errors

    def prepare(self) -> None:
        """Открывает файл, определяет кодировку, читает заголовок."""
        self._encoding = detect_encoding(self._file_path)

        with open(self._file_path, encoding=self._encoding, newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration as err:
                raise ValueError(
                    f"Файл пуст или не содержит заголовка: {self._file_path}"
                ) from err

        self._raw_columns = [h.strip() for h in header]

        if not self._schema_class.validate_headers(self._raw_columns):
            expected = set(self._schema_class.column_mapping.keys())
            actual = set(self._raw_columns)
            raise ValueError(
                f"Заголовки не соответствуют ожидаемым.\n"
                f"Ожидалось: {expected}\nПолучено: {actual}"
            )

        column_mapping = self._schema_class.get_column_mapping()
        self._column_indices = {}
        for idx, col_name in enumerate(self._raw_columns):
            if col_name in column_mapping:
                db_col_name = column_mapping[col_name]
                self._column_indices[db_col_name] = idx

        logger.debug(
            "Файл %s: колонок=%d, кодировка=%s, таблица=%s.",
            self._file_path.name,
            len(self._raw_columns),
            self._encoding,
            self.table_name,
        )

    def _parse_row(self, row: list[str]) -> dict[str, Any] | None:
        """Парсит и валидирует одну строку CSV."""
        try:
            data: dict[str, Any] = {}
            for db_col_name, idx in self._column_indices.items():
                if idx < len(row):
                    value = row[idx]
                    if db_col_name == "count":
                        data[db_col_name] = int(value)
                    else:
                        data[db_col_name] = value
                else:
                    data[db_col_name] = None

            validated = self._schema_class(**data)
            return validated.to_db_row()

        except (ValidationError, ValueError) as e:
            self._validation_errors += 1
            logger.debug(
                "Ошибка валидации строки в %s: %s",
                self._file_path.name,
                e,
            )
            return None

    def read_batches(
        self,
        month: str,
        date: str,
        time: str,
        file_path_str: str,
    ) -> Iterator[list[list[str]]]:
        """Генератор батчей строк."""
        metadata_row = [month, date, time, file_path_str]

        with open(self._file_path, encoding=self._encoding or "utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)

            batch: list[list[str]] = []
            line_num = 1
            valid_rows = 0

            for row in reader:
                line_num += 1

                validated_data = self._parse_row(row)
                if validated_data is None:
                    continue

                db_row = [
                    str(validated_data[col])
                    for col in self._schema_class.get_column_names()
                ]
                db_row.extend(metadata_row)
                batch.append(db_row)
                valid_rows += 1

                if len(batch) >= self._batch_size:
                    yield batch
                    batch = []

            if batch:
                yield batch

            logger.debug(
                "Файл %s: строк=%d, валидных=%d, ошибок=%d",
                self._file_path.name,
                line_num - 1,
                valid_rows,
                self._validation_errors,
            )