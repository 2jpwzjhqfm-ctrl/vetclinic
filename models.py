from database import get_connection


def add_client(pet_name, pet_type, owner_name, phone, reason, preferred_time,
               doctor, user_id=None, service_id=None, service_name="",
               price=0.0, discount_pct=0, points_used=0.0, final_price=0.0,
               appointment_date=""):
    """Добавляет нового клиента в базу данных
    (с данными об услуге, скидке, баллах и дате приёма)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO clients
        (pet_name, pet_type, owner_name, phone, reason, preferred_time, doctor,
         user_id, service_id, service_name, price, discount_pct,
         points_used, final_price, appointment_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pet_name, pet_type, owner_name, phone, reason, preferred_time, doctor,
          user_id, service_id, service_name, price, discount_pct,
          points_used, final_price, appointment_date))

    conn.commit()
    conn.close()


def _dict_rows(conn):
    conn.row_factory = lambda cursor, row: {
        column[0]: row[index]
        for index, column in enumerate(cursor.description)
    }
    return conn


def get_all_clients():
    """Возвращает список ВСЕХ клиентов (для администратора)."""
    conn = _dict_rows(get_connection())
    clients = conn.execute('SELECT * FROM clients ORDER BY created_at DESC').fetchall()
    conn.close()
    return clients


def get_clients_by_user(user_id):
    """Возвращает записи ТОЛЬКО одного пользователя (для личного кабинета)."""
    conn = _dict_rows(get_connection())
    clients = conn.execute(
        'SELECT * FROM clients WHERE user_id = ? ORDER BY appointment_date DESC, created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return clients


def is_time_busy(doctor, preferred_time, appointment_date=""):
    """Проверяет, занято ли это время у этого врача в этот день."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM clients WHERE doctor = ? AND preferred_time = ? AND appointment_date = ?',
        (doctor, preferred_time, appointment_date))
    result = cursor.fetchone()
    conn.close()
    return result is not None
