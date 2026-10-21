import sqlite3

# Имя файла базы данных (создастся автоматически)
DATABASE_NAME = 'clients.db'

def get_connection():
    """Возвращает соединение с базой данных."""
    return sqlite3.connect(DATABASE_NAME)

def init_db():
    """Создает таблицу клиентов, если её ещё нет."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_name TEXT NOT NULL,
            pet_type TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            reason TEXT,
            preferred_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("База данных SQLite готова к работе.")

if __name__ == "__main__":
    init_db()