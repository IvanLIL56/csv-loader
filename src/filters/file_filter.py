"""
Фильтр файлов по имени.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..schemas.models import get_supported_filenames

logger = logging.getLogger(__name__)


class FileFilter:
    """Фильтр файлов по списку разрешённых имён."""

    def __init__(
        self,
        allowed_filenames: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        self.allowed_filenames = allowed_filenames or get_supported_filenames()
        self.exclude_patterns = exclude_patterns or []

    def matches(self, file_path: Path) -> bool:
        """Проверяет, соответствует ли файл критериям фильтра."""
        filename = file_path.name

        if filename not in self.allowed_filenames:
            logger.debug(
                "Файл %s пропущен: не входит в список разрешённых",
                filename,
            )
            return False

        for exclude_pattern in self.exclude_patterns:
            if exclude_pattern in filename:
                logger.debug("Файл исключён по паттерну: %s", file_path)
                return False

        return True

    def filter_files(self, files: list[Path]) -> list[Path]:
        """Фильтрует список файлов по заданным критериям."""
        filtered = [f for f in files if self.matches(f)]
        logger.info(
            "Отфильтровано файлов: %d из %d (разрешённые: %s)",
            len(filtered),
            len(files),
            self.allowed_filenames,
        )
        return filtered