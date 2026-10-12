"""
Pydantic-модели для валидации CSV-файлов.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pydantic import BaseModel, field_validator


class BaseCSVSchema(BaseModel):
    """Базовый класс для схем CSV-файлов."""

    column_mapping: ClassVar[dict[str, str]] = {}
    table_name: ClassVar[str] = ""

    @classmethod
    def get_column_mapping(cls) -> dict[str, str]:
        """Возвращает маппинг колонок."""
        return cls.column_mapping

    @classmethod
    def get_table_name(cls) -> str:
        """Возвращает имя таблицы."""
        return cls.table_name

    @classmethod
    def get_column_names(cls) -> list[str]:
        """Возвращает список латинских имён колонок."""
        return list(cls.column_mapping.values())

    @classmethod
    def validate_headers(cls, headers: list[str]) -> bool:
        """Проверяет, что заголовки CSV соответствуют ожидаемым."""
        expected = set(cls.column_mapping.keys())
        actual = set(h.strip() for h in headers)
        return expected.issubset(actual)

    def to_db_row(self) -> dict[str, Any]:
        """Преобразует модель в словарь для вставки в БД."""
        result = {}
        for _ru_name, en_name in self.column_mapping.items():
            result[en_name] = getattr(self, en_name)
        return result


class PhoneNumberSchema(BaseCSVSchema):
    """Схема для файла phone_number.csv."""

    column_mapping: ClassVar[dict[str, str]] = {
        "Номер телефона": "phone_number",
        "date": "date",
        "count": "count",
        "country": "country",
    }
    table_name: ClassVar[str] = "phone_number"

    phone_number: str
    date: str
    count: int
    country: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Валидирует номер телефона."""
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 10:
            raise ValueError(f"Номер телефона слишком короткий: {v}")
        return cleaned

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Валидирует count."""
        if v < 0:
            raise ValueError(f"count не может быть отрицательным: {v}")
        return v


class AccountNumberSchema(BaseCSVSchema):
    """Схема для файла account_number.csv."""

    column_mapping: ClassVar[dict[str, str]] = {
        "Номер счета": "account_number",
        "БИК": "bik",
        "date": "date",
        "count": "count",
        "country": "country",
    }
    table_name: ClassVar[str] = "account_number"

    account_number: str
    bik: str
    date: str
    count: int
    country: str

    @field_validator("account_number")
    @classmethod
    def validate_account(cls, v: str) -> str:
        """Валидирует номер счёта."""
        cleaned = re.sub(r"\s+", "", v)
        if not cleaned.isdigit():
            raise ValueError(f"Номер счёта должен содержать только цифры: {v}")
        if len(cleaned) != 20:
            raise ValueError(f"Номер счёта должен содержать 20 цифр: {v}")
        return cleaned

    @field_validator("bik")
    @classmethod
    def validate_bik(cls, v: str) -> str:
        """Валидирует БИК."""
        cleaned = re.sub(r"\s+", "", v)
        if not cleaned.isdigit():
            raise ValueError(f"БИК должен содержать только цифры: {v}")
        if len(cleaned) != 9:
            raise ValueError(f"БИК должен содержать 9 цифр: {v}")
        return cleaned

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Валидирует count."""
        if v < 0:
            raise ValueError(f"count не может быть отрицательным: {v}")
        return v


class CardNumberSchema(BaseCSVSchema):
    """Схема для файла card_number.csv."""

    column_mapping: ClassVar[dict[str, str]] = {
        "Номер карты": "card_number",
        "date": "date",
        "count": "count",
        "country": "country",
    }
    table_name: ClassVar[str] = "card_number"

    card_number: str
    date: str
    count: int
    country: str

    @field_validator("card_number")
    @classmethod
    def validate_card(cls, v: str) -> str:
        """Валидирует номер карты."""
        cleaned = re.sub(r"\s+", "", v)
        if not cleaned.isdigit():
            raise ValueError(f"Номер карты должен содержать только цифры: {v}")
        if len(cleaned) < 13 or len(cleaned) > 19:
            raise ValueError(
                f"Номер карты должен содержать от 13 до 19 цифр: {v}"
            )
        return cleaned

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Валидирует count."""
        if v < 0:
            raise ValueError(f"count не может быть отрицательным: {v}")
        return v


class InnSchema(BaseCSVSchema):
    """Схема для файла inn.csv."""

    column_mapping: ClassVar[dict[str, str]] = {
        "ИНН": "inn",
        "date": "date",
        "count": "count",
        "country": "country",
    }
    table_name: ClassVar[str] = "inn"

    inn: str
    date: str
    count: int
    country: str

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: str) -> str:
        """Валидирует ИНН."""
        cleaned = re.sub(r"\s+", "", v)
        if not cleaned.isdigit():
            raise ValueError(f"ИНН должен содержать только цифры: {v}")
        if len(cleaned) not in (10, 12):
            raise ValueError(f"ИНН должен содержать 10 или 12 цифр: {v}")
        return cleaned

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Валидирует count."""
        if v < 0:
            raise ValueError(f"count не может быть отрицательным: {v}")
        return v


class PassportHashSchema(BaseCSVSchema):
    """Схема для файла passport_hash.csv."""

    column_mapping: ClassVar[dict[str, str]] = {
        "Хеш паспорта": "passport_hash",
        "date": "date",
        "count": "count",
        "country": "country",
    }
    table_name: ClassVar[str] = "passport_hash"

    passport_hash: str
    date: str
    count: int
    country: str

    @field_validator("passport_hash")
    @classmethod
    def validate_passport_hash(cls, v: str) -> str:
        """Валидирует хеш паспорта."""
        cleaned = re.sub(r"\s+", "", v).lower()

        if not re.match(r"^[0-9a-f]+$", cleaned):
            raise ValueError(
                f"Хеш паспорта должен содержать только hex-символы: {v}"
            )

        valid_lengths = {32, 40, 64}
        if len(cleaned) not in valid_lengths:
            raise ValueError(
                f"Хеш паспорта должен иметь длину {valid_lengths}, "
                f"получено: {len(cleaned)}"
            )

        return cleaned

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Валидирует count."""
        if v < 0:
            raise ValueError(f"count не может быть отрицательным: {v}")
        return v


FILE_SCHEMA_REGISTRY: dict[str, type[BaseCSVSchema]] = {
    "phone_number.csv": PhoneNumberSchema,
    "account_number.csv": AccountNumberSchema,
    "card_number.csv": CardNumberSchema,
    "inn.csv": InnSchema,
    "passport_hash.csv": PassportHashSchema,
}


def get_schema_for_file(filename: str) -> type[BaseCSVSchema] | None:
    """Возвращает класс схемы для указанного имени файла."""
    return FILE_SCHEMA_REGISTRY.get(filename)


def get_supported_filenames() -> list[str]:
    """Возвращает список поддерживаемых имён файлов."""
    return list(FILE_SCHEMA_REGISTRY.keys())