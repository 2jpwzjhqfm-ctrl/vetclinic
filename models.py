from database import get_connection

def add_client(pet_name, pet_type, owner_name, phone, reason, preferred_time, doctor):
    """Добавляет нового клиента в базу данных."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO clients (pet_name, pet_type, owner_name, phone, reason, preferred_time, doctor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (pet_name, pet_type, owner_name, phone, reason, preferred_time, doctor))
    
    conn.commit()
    conn.close()

def get_all_clients():
    """Возвращает список всех клиентов."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM clients ORDER BY created_at DESC')
    clients = cursor.fetchall()
    
    conn.close()
    return clients

def is_time_busy(doctor, preferred_time):
    """Проверяет, занято ли это время у этого врача."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients WHERE doctor = ? AND preferred_time = ?', (doctor, preferred_time))
    result = cursor.fetchone()
    conn.close()
    return result is not None