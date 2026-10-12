import csv
import random
import os
from datetime import datetime, timedelta

# ============================================================
#  РЕЖИМ ГЕНЕРАЦИИ ДАННЫХ
#  "random"    — каждое значение новое
#  "pool"      — общий пул, значения повторяются между файлами
#  "fixed"     — весь пул целиком в каждом файле
# ============================================================
MODE = "pool"
POOL_SIZE = 100
ROWS_PER_FILE = 30

# ---------- Параметры директорий ----------
BASE_DIR = "tests"
YEAR = 2026

MONTHS = [
    "01_январь",  "02_февраль", "03_март",     "04_апрель",
    "05_май",     "06_июнь",    "07_июль",     "08_август",
    "09_сентябрь","10_октябрь", "11_ноябрь",   "12_декабрь",
]
MONTHS_TO_USE = MONTHS[4:10]
DAYS_PER_MONTH = 15
TIMES = [(9, 0), (12, 30), (18, 0)]


# ---------- Генераторы одиночных значений ----------
def rand_country():
    return random.choice(["RU", "KZ", "BY"])

def rand_count():
    return random.randint(1, 1000)

def gen_phone():
    return f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"

def gen_account():
    return "".join(str(random.randint(0, 9)) for _ in range(20))

def gen_bik():
    return "04" + "".join(str(random.randint(0, 9)) for _ in range(7))

def gen_card():
    return "9999" + "".join(str(random.randint(0, 9)) for _ in range(12))

def gen_inn():
    return "".join(str(random.randint(0, 9)) for _ in range(10))

def gen_passport_hash():
    # 64 hex-символа — имитация SHA-256
    return "".join(random.choice("0123456789abcdef") for _ in range(64))


# ---------- Пул значений ----------
POOL = {
    "phone":    [gen_phone()    for _ in range(POOL_SIZE)],
    "account":  [(gen_account(), gen_bik()) for _ in range(POOL_SIZE)],
    "card":     [gen_card()     for _ in range(POOL_SIZE)],
    "inn":      [gen_inn()      for _ in range(POOL_SIZE)],
    "passport": [gen_passport_hash() for _ in range(POOL_SIZE)],
}


def rand_date():
    start = datetime(YEAR, 1, 1)
    return (start + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")


# ---------- Сборка строки для каждого типа файла ----------
def row_phone(key=None):
    value = key if key else gen_phone()
    return [value, rand_date(), rand_count(), rand_country()]

def row_account(key=None):
    acc, bik = key if key else (gen_account(), gen_bik())
    return [acc, bik, rand_date(), rand_count(), rand_country()]

def row_card(key=None):
    value = key if key else gen_card()
    return [value, rand_date(), rand_count(), rand_country()]

def row_inn(key=None):
    value = key if key else gen_inn()
    return [value, rand_date(), rand_count(), rand_country()]

def row_passport(key=None):
    value = key if key else gen_passport_hash()
    return [value, rand_date(), rand_count(), rand_country()]


FILE_TYPES = [
    ("phone_number.csv",
     ["Номер телефона", "date", "count", "country"],
     "phone", row_phone),
    ("account_number.csv",
     ["Номер счета", "БИК", "date", "count", "country"],
     "account", row_account),
    ("card_number.csv",
     ["Номер карты", "date", "count", "country"],
     "card", row_card),
    ("inn.csv",
     ["ИНН", "date", "count", "country"],
     "inn", row_inn),
    ("passport_hash.csv",
     ["Хеш паспорта", "date", "count", "country"],
     "passport", row_passport),
]


def build_rows(pool_key, row_builder):
    if MODE == "random":
        return [row_builder() for _ in range(ROWS_PER_FILE)]

    if MODE == "pool":
        n = min(ROWS_PER_FILE, len(POOL[pool_key]))
        keys = random.sample(POOL[pool_key], n)
        return [row_builder(k) for k in keys]

    if MODE == "fixed":
        keys = list(POOL[pool_key])
        return [row_builder(k) for k in keys]

    raise ValueError(f"Неизвестный MODE: {MODE}")


def write_file(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def main():
    total_dirs = 0
    total_files = 0

    for month_idx, month_name in enumerate(MONTHS_TO_USE):
        month_num = month_idx + 1
        days_in_month = 30 if month_num in (4, 6, 9, 11) else 28 if month_num == 2 else 31
        days = sorted(random.sample(range(1, days_in_month + 1), DAYS_PER_MONTH))

        for day in days:
            date_folder = f"{day:02d}.{month_num:02d}.{YEAR}"
            for hour, minute in TIMES:
                time_folder = f"{hour} {minute:02d}"
                leaf_dir = os.path.join(BASE_DIR, month_name, date_folder, time_folder)
                os.makedirs(leaf_dir, exist_ok=True)
                total_dirs += 1

                for filename, headers, pool_key, row_builder in FILE_TYPES:
                    rows = build_rows(pool_key, row_builder)
                    write_file(os.path.join(leaf_dir, filename), headers, rows)
                    total_files += 1

    print(f"MODE = {MODE}")
    print(f"Директорий: {total_dirs}, файлов: {total_files}")
    print(f"Корень: {os.path.abspath(BASE_DIR)}")


if __name__ == "__main__":
    main()