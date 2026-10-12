#!/usr/bin/env bash
#
# setup_project.sh
# Скрипт для создания структуры проекта CSV-to-PostgreSQL Loader.
#
# Использование:
#   chmod +x setup_project.sh
#   ./setup_project.sh [путь_куда_создать]
#
# Если путь не указан, проект создаётся в ./csv_loader в текущей директории.
#

set -euo pipefail

# ──────────────────────────────────────────────
# Параметры
# ──────────────────────────────────────────────

PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(realpath -m "$PROJECT_DIR")"

echo "📦 Создание проекта в: $PROJECT_DIR"

# ──────────────────────────────────────────────
# Создание директорий
# ──────────────────────────────────────────────

mkdir -p "$PROJECT_DIR/src"
mkdir -p "$PROJECT_DIR/tests"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/scripts"

echo "✅ Директории созданы."

# ──────────────────────────────────────────────
# requirements.txt
# ──────────────────────────────────────────────

cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
psycopg2-binary>=2.9.9
pydantic>=2.5.0
tqdm>=4.66.0
EOF

# ──────────────────────────────────────────────
# pyproject.toml (настройки ruff и mypy)
# ──────────────────────────────────────────────

cat > "$PROJECT_DIR/pyproject.toml" << 'EOF'
[project]
name = "csv-loader"
version = "1.0.0"
description = "Загрузка CSV-файлов в PostgreSQL с очередью задач"
requires-python = ">=3.10"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["F", "E", "W", "I"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
warn_unused_ignores = true
show_error_codes = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["psycopg2.*"]
ignore_missing_imports = true
EOF

# ──────────────────────────────────────────────
# .gitignore
# ──────────────────────────────────────────────

cat > "$PROJECT_DIR/.gitignore" << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/
.mypy_cache/
.ruff_cache/
.pytest_cache/
logs/*.log
.env
EOF

# ──────────────────────────────────────────────
# README.md
# ──────────────────────────────────────────────

cat > "$PROJECT_DIR/README.md" << 'EOF'
# CSV-to-PostgreSQL Loader

Программа для массового параллельного парсинга CSV-файлов и загрузки их в PostgreSQL.
Поддерживает очередь задач, многопоточность, потоковое чтение и восстановление после сбоев.

## Структура проекта
