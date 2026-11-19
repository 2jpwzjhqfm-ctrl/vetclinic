import sqlite3

DATABASE_NAME = "clients.db"


def get_connection():
    """Возвращает соединение с базой данных."""
    return sqlite3.connect(DATABASE_NAME)


def _ensure_columns(conn):
    """Мягкая миграция: добавляет недостающие колонки в clients,
    не трогая существующие данные."""
    cursor = conn.execute("PRAGMA table_info(clients)")
    existing = {row[1] for row in cursor.fetchall()}

    needed = {
        "doctor": "TEXT DEFAULT 'Любой врач'",
        "user_id": "INTEGER",
        "service_id": "INTEGER",
        "service_name": "TEXT DEFAULT ''",
        "price": "REAL DEFAULT 0",
        "discount_pct": "INTEGER DEFAULT 0",
        "points_used": "REAL DEFAULT 0",
        "final_price": "REAL DEFAULT 0",
        "appointment_date": "TEXT DEFAULT ''",
    }
    for name, ddl in needed.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE clients ADD COLUMN {name} {ddl}")
    conn.commit()


def init_db():
    """Создаёт таблицы клиентов и услуг."""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица клиентов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_name TEXT NOT NULL,
            pet_type TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            reason TEXT,
            preferred_time TEXT,
            doctor TEXT DEFAULT 'Любой врач',
            user_id INTEGER,
            service_id INTEGER,
            service_name TEXT DEFAULT '',
            price REAL DEFAULT 0,
            discount_pct INTEGER DEFAULT 0,
            points_used REAL DEFAULT 0,
            final_price REAL DEFAULT 0,
            appointment_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_columns(conn)

    # Таблица услуг
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            duration_minutes INTEGER,
            category TEXT,
            image TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Услуги нашей ветеринарной клиники
    services = [
        (
            "Первичный приём ветеринара",
            "Осмотр питомца, консультация ветеринарного врача и составление рекомендаций.",
            1500,
            30,
            "Консультация",
            "services 1.jpg"
        ),
        (
            "Повторный приём ветеринара",
            "Повторная консультация и контроль состояния питомца.",
            1000,
            20,
            "Консультация",
            "services 2.jpg"
        ),
        (
            "Вакцинация",
            "Профилактическая вакцинация домашних животных.",
            1800,
            30,
            "Профилактика",
            "services 3.jpg"
        ),
        (
            "Диагностика",
            "Комплексный диагностический осмотр питомца.",
            2000,
            40,
            "Диагностика",
            "services 4.jpg"
        ),
        (
            "Лечение",
            "Консультация и лечение заболеваний домашних животных.",
            2500,
            60,
            "Лечение",
            "services 5.jpg"
        ),
        (
            "Уход за животным",
            "Гигиенические процедуры и уход за домашним питомцем.",
            1200,
            45,
            "Уход",
            "services 6.jpg"
        )
    ]

    # Добавляем услуги только если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM services")
    services_count = cursor.fetchone()[0]

    if services_count == 0:
        cursor.executemany("""
            INSERT INTO services
            (name, description, price, duration_minutes, category, image)
            VALUES (?, ?, ?, ?, ?, ?)
        """, services)

    conn.commit()
    conn.close()

    print("База данных SQLite готова к работе.")


if __name__ == "__main__":
    init_db()
