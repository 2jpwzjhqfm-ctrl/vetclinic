import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import init_db, get_connection
from models import add_client, get_all_clients, get_clients_by_user, is_time_busy
from account import (
    account_bp,
    init_db as init_account_db,
    get_db as get_account_db,
    current_user,
    level_for,
    POINTS_PER_VISIT,
)

app = Flask(
    __name__,
    template_folder="pages",
    static_folder=".",
    static_url_path=""
)

# Ключ для сессий (вход, выход, личный кабинет)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")

# Инициализация баз данных при запуске
init_db()            # база записи клиентов (clients.db)
init_account_db()    # база аккаунтов (clinic.db: users, visits, pets)

# Подключаем модуль личного кабинета
app.register_blueprint(account_bp)

# Максимум чека, который можно закрыть баллами (0.5 = не больше половины)
MAX_POINTS_SHARE = 0.5

# Пароль администратора (меняйте на свой)
ADMIN_PASSWORD = "vet-1234"


def dict_cursor(conn):
    conn.row_factory = lambda cursor, row: {
        column[0]: row[index]
        for index, column in enumerate(cursor.description)
    }
    return conn


def get_user_loyalty():
    """Возвращает словарь с данными карты лояльности вошедшего пользователя
    или None, если гость."""
    user = current_user()
    if not user:
        return None

    with get_account_db() as db:
        visits_count = db.execute(
            "SELECT COUNT(*) AS n FROM visits WHERE user_id = ?",
            (user["id"],)
        ).fetchone()["n"]

    level = level_for(visits_count)
    return {
        "user_id": user["id"],
        "name": user["name"],
        "points": user["points"],
        "discount": level["discount"],
        "level_name": level["name"],
        "visits_count": visits_count,
    }


def is_admin():
    return session.get("is_admin") is True


@app.context_processor
def inject_upcoming_appointments():
    """Прокидывает предстоящие приёмы вошедшего пользователя во ВСЕ шаблоны
    (в том числе в личный кабинет — для блока напоминаний)."""
    user = current_user()
    if not user:
        return {}

    conn = dict_cursor(get_connection())
    upcoming = conn.execute(
        """SELECT pet_name, doctor, service_name,
                  appointment_date, preferred_time
           FROM clients
           WHERE user_id = ? AND appointment_date >= ?
           ORDER BY appointment_date, preferred_time""",
        (user["id"], date.today().isoformat()),
    ).fetchall()
    conn.close()

    return {"upcoming_appointments": upcoming}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/services")
def services():
    """Показывает список услуг из базы данных."""
    conn = dict_cursor(get_connection())

    services_from_db = conn.execute("""
        SELECT id, name, description, price,
               duration_minutes, category, image
        FROM services
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()

    conn.close()

    return render_template(
        "services.html",
        services=services_from_db
    )


@app.route("/services/<int:service_id>")
def service_detail(service_id):
    """Показывает подробную информацию об одной услуге."""
    conn = dict_cursor(get_connection())

    service = conn.execute("""
        SELECT id, name, description, price,
               duration_minutes, category, image
        FROM services
        WHERE id = ? AND is_active = 1
    """, (service_id,)).fetchone()

    conn.close()

    if service is None:
        return "Услуга не найдена", 404

    return render_template(
        "service_detail.html",
        service=service
    )


@app.route("/specialists")
def specialists():
    return render_template("specialists.html")


@app.route("/appointment")
def appointment():
    service_id = request.args.get("service_id", type=int)
    selected_service = None
    doctor = request.args.get("doctor", "Любой врач")
    selected_date = request.args.get("appointment_date", "")

    # Список врачей для выпадающего списка (Имя: Специализация)
    doctors_list = {
        "Анна Смирнова": "Терапевт (осмотры, вакцинация, лечение внутренних болезней)",
        "Иван Петров": "Хирург (плановые и экстренные операции, травматология)",
        "Елена Козлова": "Дерматолог (кожные заболевания, аллергии)",
        "Дмитрий Волков": "Стоматолог (гигиена полости рта, лечение зубов)"
    }

    # Список услуг для выпадающего списка в форме записи
    conn = dict_cursor(get_connection())
    services_from_db = conn.execute("""
        SELECT id, name, price
        FROM services
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()

    if service_id is not None:
        selected_service = conn.execute("""
            SELECT id, name, description, price, duration_minutes, category, image
            FROM services WHERE id = ? AND is_active = 1
        """, (service_id,)).fetchone()
    conn.close()

    # Данные карты лояльности (для гостей — None)
    loyalty = get_user_loyalty()

    return render_template(
        "appointment.html",
        selected_service=selected_service,
        doctor=doctor,
        selected_date=selected_date,
        doctors_list=doctors_list,
        services=services_from_db,
        today=date.today().isoformat(),
        is_logged_in=loyalty is not None,
        loyalty=loyalty,
        max_points_share=MAX_POINTS_SHARE,
        earn_per_visit=POINTS_PER_VISIT,
    )


@app.route("/contacts")
def contacts():
    return render_template("contacts.html")


@app.route("/add_client", methods=["POST"])
def add_client_route():
    """Обрабатывает форму записи на приём.
    Для вошедшего пользователя применяет скидку и списывает баллы."""
    pet_name = request.form.get("pet_name")
    pet_type = request.form.get("pet_type")
    owner_name = request.form.get("owner_name")
    phone = request.form.get("phone")
    reason = request.form.get("reason", "")
    preferred_time = request.form.get("preferred_time", "")
    doctor = request.form.get("doctor", "Любой врач")
    appointment_date = request.form.get("appointment_date", "")

    # Данные об услуге и баллах
    service_id = request.form.get("service_id", type=int)
    points_requested = request.form.get("points_to_use", type=int) or 0

    if pet_name and owner_name and phone and preferred_time:
        # Дата обязательна и не может быть в прошлом
        if not appointment_date:
            flash("Пожалуйста, выберите дату приёма.", "error")
            return redirect(url_for("appointment", doctor=doctor))

        if appointment_date < date.today().isoformat():
            flash("Нельзя записаться на прошедшую дату. Выберите день начиная с сегодняшнего.", "error")
            return redirect(url_for("appointment", doctor=doctor, appointment_date=appointment_date))

        # Проверка занятости: врач + дата + время
        if is_time_busy(doctor, preferred_time, appointment_date):
            flash(f"Увы, {doctor} уже занят(а) {appointment_date} в это время. Выберите другое.", "error")
            return redirect(url_for("appointment", doctor=doctor, appointment_date=appointment_date))

        # --- Расчёт цены со скидкой и баллами ---
        price = 0.0
        service_name = ""
        if service_id is not None:
            conn = dict_cursor(get_connection())
            row = conn.execute(
                "SELECT id, name, price FROM services WHERE id = ? AND is_active = 1",
                (service_id,)
            ).fetchone()
            conn.close()
            if row:
                service_id = row["id"]
                service_name = row["name"]
                price = float(row["price"])

        loyalty = get_user_loyalty()
        discount_pct = loyalty["discount"] if loyalty else 0
        user_points = loyalty["points"] if loyalty else 0

        # Цена после скидки уровня
        price_after_discount = round(price * (1 - discount_pct / 100.0), 2)

        # Списание баллов: не больше, чем есть на счету,
        # и не больше MAX_POINTS_SHARE от чека после скидки
        max_points = int(min(user_points, price_after_discount * MAX_POINTS_SHARE))
        points_used = max(0, min(points_requested, max_points))

        final_price = round(price_after_discount - points_used, 2)

        add_client(
            pet_name, pet_type, owner_name, phone,
            reason, preferred_time, doctor,
            user_id=loyalty["user_id"] if loyalty else None,
            service_id=service_id,
            service_name=service_name,
            price=price,
            discount_pct=discount_pct,
            points_used=points_used,
            final_price=final_price,
            appointment_date=appointment_date,
        )

        # Начисление баллов за визит + фиксация визита в истории
        # (дата визита = дата приёма, поэтому визит синхронизирован с записью)
        if loyalty:
            with get_account_db() as db:
                db.execute(
                    "INSERT INTO visits (user_id, service, amount, visit_date) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        loyalty["user_id"],
                        service_name or "Приём",
                        final_price,
                        appointment_date or date.today().isoformat(),
                    )
                )
                db.execute(
                    "UPDATE users SET points = points + ? WHERE id = ?",
                    (POINTS_PER_VISIT, loyalty["user_id"]),
                )

            parts = []
            if discount_pct:
                parts.append(f"скидка {discount_pct}% = −{round(price - price_after_discount, 2)} ₽")
            if points_used:
                parts.append(f"списано {points_used} балл(ов)")
            summary = "; ".join(parts) if parts else "без скидок"
            flash(
                f"Запись создана на {appointment_date}, {preferred_time}! "
                f"Услуга: {service_name or '—'}. "
                f"Итого к оплате: {final_price} ₽ ({summary}). "
                f"Начислено +{POINTS_PER_VISIT} баллов.",
                "success",
            )
            return redirect(url_for("my_appointments"))
        else:
            flash("Заявка отправлена! Мы свяжемся с вами для подтверждения.", "success")
            return redirect(url_for("appointment"))

    return redirect(url_for("appointment"))


@app.route("/my_appointments")
def my_appointments():
    """Страница «Мои записи» — только записи вошедшего пользователя."""
    loyalty = get_user_loyalty()
    if loyalty is None:
        return redirect("/login")

    appointments = get_clients_by_user(loyalty["user_id"])

    return render_template(
        "my_appointments.html",
        appointments=appointments,
        user_name=loyalty["name"],
        today=date.today().isoformat(),
        is_logged_in=True,
    )


# ---------- АДМИНИСТРАТИВНАЯ ЧАСТЬ ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Отдельный вход для администраторов (работников клиники)."""
    error = None
    if request.method == "POST":
        login = request.form.get("login", "")
        password = request.form.get("password", "")
        if login == "admin" and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_clients"))
        error = "Неверный логин или пароль администратора."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/clients")
def admin_clients():
    """Список всех записей — доступен только администратору."""
    if not is_admin():
        return redirect(url_for("admin_login"))

    clients = get_all_clients()
    return render_template(
        "admin_clients.html",
        clients=clients
    )


@app.route("/admin/users")
def admin_users():
    """Список всех зарегистрированных пользователей — только для админа."""
    if not is_admin():
        return redirect(url_for("admin_login"))

    with get_account_db() as db:
        cur = db.execute("SELECT * FROM users ORDER BY id")
        column_names = [description[0] for description in cur.description]
        raw_rows = cur.fetchall()

        visit_counts = {
            row["user_id"]: row["n"]
            for row in db.execute(
                "SELECT user_id, COUNT(*) AS n FROM visits GROUP BY user_id"
            ).fetchall()
        }

    # Пароли (даже хеши) в таблицу не показываем
    hide_columns = {"password_hash", "password"}

    columns = [c for c in column_names if c not in hide_columns]
    if "card_number" not in columns:
        columns.insert(0, "card_number")
    if "visits_count" not in columns:
        columns.append("visits_count")

    users = []
    for row in raw_rows:
        user_row = dict(zip(column_names, [row[i] for i in range(len(column_names))]))
        user_row["visits_count"] = visit_counts.get(user_row.get("id"), 0)
        # Номер карты лояльности: HP + id из базы
        user_row["card_number"] = "HP-{:06d}".format(user_row.get("id") or 0)
        users.append(user_row)

    return render_template(
        "admin_users.html",
        columns=columns,
        users=users
    )


if __name__ == "__main__":
    app.run(debug=True, port=5007)
