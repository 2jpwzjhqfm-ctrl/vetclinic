
import sqlite3
from pathlib import Path

# Путь к файлу базы данных
DB_PATH = Path(__file__).resolve().parent / "clinic.db"

# Услуги нашей ветеринарной клиники
services = [
    (
        1, "Приём ветеринара",
        "Первичный и профилактический осмотр питомца, консультация врача.",
        1200, 30, "Консультация", "services 2.jpg"
    ),
    (
        2, "Вакцинация",
        "Плановая вакцинация кошек и собак.",
        1800, 30, "Профилактика", "services 3.jpg"
    ),
    (
        3, "УЗИ-диагностика",
        "Ультразвуковое исследование внутренних органов.",
        2000, 40, "Диагностика", "services 4.jpg"
    ),
    (
        4, "Анализы",
        "Лабораторные исследования для диагностики и контроля лечения.",
        900, 20, "Диагностика", "services 5.jpg"
    ),
    (
        5, "Хирургия",
        "Хирургические вмешательства с предварительным обследованием.",
        5000, 120, "Лечение", "services 6.jpg"
    ),
    (
        6, "Стоматология",
        "Осмотр полости рта и помощь при заболеваниях зубов.",
        2500, 45, "Лечение", "services 7.jpg"
    ),
    (
        7, "Дерматология",
        "Диагностика проблем кожи, шерсти и аллергических реакций.",
        1800, 40, "Лечение", "services 8.jpg"
    ),
    (
        8, "Стационар",
        "Наблюдение за питомцами и уход после процедур.",
        3000, 1440, "Уход", "services 9.jpg"
    ),
]

with sqlite3.connect(DB_PATH) as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            category TEXT NOT NULL,
            image TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    connection.executemany("""
        INSERT OR IGNORE INTO services
        (id, name, description, price, duration_minutes, category, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, services)

    count = connection.execute(
        "SELECT COUNT(*) FROM services"
    ).fetchone()[0]

print(f"База данных создана: {DB_PATH}")
print(f"Количество услуг в базе: {count}")
