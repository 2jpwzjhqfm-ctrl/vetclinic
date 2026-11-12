import os
import sqlite3
import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clinic.db")   
CSS_DIR = os.path.join(BASE_DIR, "css")         

ADMIN_CODE = os.environ.get("ADMIN_CODE", "vet-1234")

#  Правила программы лояльности (меняются в одном месте) 
POINTS_PER_VISIT = 100       
RUB_PER_POINT = 1            
LEVELS = [
    {"slug": "standard", "name": "Стандарт",   "min_visits": 0,  "discount": 0},
    {"slug": "silver",   "name": "Серебряный", "min_visits": 5,  "discount": 5},
    {"slug": "gold",     "name": "Золотой",    "min_visits": 10, "discount": 10},
]

# Модуль личного кабинета 
account_bp = Blueprint("account", __name__, template_folder="templates")
 
@account_bp.route("/css/account.css")
def account_css():
    return send_from_directory(CSS_DIR, "account.css", mimetype="text/css")


#  База данных 
def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            points        INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visits (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            service    TEXT NOT NULL,
            amount     REAL NOT NULL DEFAULT 0,
            visit_date TEXT NOT NULL
        );
                CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            animal_type TEXT NOT NULL,
            breed TEXT,
            birth_date TEXT,
            sex TEXT DEFAULT 'Не указан',
            weight REAL,
            color TEXT,
            health_notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_pets_user_id
        ON pets(user_id);
                CREATE TABLE IF NOT EXISTS pet_health_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            pet_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL DEFAULT (date('now', 'localtime')),

            appetite TEXT NOT NULL DEFAULT 'Обычный',
            activity TEXT NOT NULL DEFAULT 'Обычная',
            wellbeing TEXT NOT NULL DEFAULT 'Хорошее',
            water_intake TEXT NOT NULL DEFAULT 'Обычное',

            walked INTEGER NOT NULL DEFAULT 0,
            played INTEGER NOT NULL DEFAULT 0,
            medication_given INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (pet_id)
                REFERENCES pets(id)
                ON DELETE CASCADE,

            UNIQUE (pet_id, entry_date),

            CHECK (appetite IN ('Слабый', 'Обычный', 'Хороший')),
            CHECK (activity IN ('Низкая', 'Обычная', 'Высокая')),
            CHECK (wellbeing IN ('Хорошее', 'Обычное', 'Есть изменения')),
            CHECK (water_intake IN ('Меньше обычного', 'Обычное', 'Больше обычного')),

            CHECK (walked IN (0, 1)),
            CHECK (played IN (0, 1)),
            CHECK (medication_given IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS vaccinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_id INTEGER NOT NULL,
            vaccine_name TEXT NOT NULL,
            date_done TEXT NOT NULL,
            next_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
        );
        """)


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Войдите, чтобы открыть личный кабинет.", "error")
            return redirect(url_for("account.login"))
        return view(*args, **kwargs)
    return wrapper


def visits_word(n):
    """Склонение слова 'визит': 1 визит, 2 визита, 5 визитов."""
    n = abs(int(n)) % 100
    if 11 <= n <= 19:
        return "визитов"
    d = n % 10
    if d == 1:
        return "визит"
    if 2 <= d <= 4:
        return "визита"
    return "визитов"


def level_for(visits_count):
    lvl = LEVELS[0]
    for candidate in LEVELS:
        if visits_count >= candidate["min_visits"]:
            lvl = candidate
    return lvl


def next_level_for(visits_count):
    for candidate in LEVELS:
        if visits_count < candidate["min_visits"]:
            return candidate
    return None
def pet_age_label(birth_date):
    """Рассчитывает возраст питомца по дате рождения."""
    if not birth_date:
        return "Не указан"

    try:
        born = datetime.date.fromisoformat(birth_date)
    except ValueError:
        return "Не указан"

    today = datetime.date.today()

    years = today.year - born.year
    months = today.month - born.month

    if today.day < born.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    if years > 0:
        if months > 0:
            return f"{years} г. {months} мес."
        return f"{years} г."

    if months > 0:
        return f"{months} мес."

    days = (today - born).days
    return f"{days} дн." if days > 0 else "Меньше дня"
# =====================================
# ПРИВИВКИ И ОБРАБОТКИ
# =====================================

SOON_DAYS = 30  # за сколько дней предупреждать

def vaccination_status(next_date_str):
    """Статус прививки по дате следующей процедуры."""
    if not next_date_str:
        return {"code": "ok", "label": "Актуально", "days_left": None}
    try:
        next_date = datetime.date.fromisoformat(next_date_str)
    except ValueError:
        return {"code": "ok", "label": "Актуально", "days_left": None}
    days = (next_date - datetime.date.today()).days
    if days < 0:
        return {"code": "overdue", "label": "Просрочено", "days_left": days}
    if days <= SOON_DAYS:
        return {"code": "soon",
                "label": "Скоро (через {} дн.)".format(days),
                "days_left": days}
    return {"code": "ok", "label": "Актуально", "days_left": days}
# ===============================
# УПРАВЛЕНИЕ ПИТОМЦАМИ
# ===============================

ANIMAL_TYPES = (
    "Собака", "Кошка", "Грызун", "Птица", "Рептилия", "Другое"
)

PET_SEX_OPTIONS = ("Самец", "Самка", "Не указан")


def validate_pet_form(form):
    """Проверка данных питомца перед сохранением."""

    data = {
        "name": form.get("name", "").strip(),
        "animal_type": form.get("animal_type", "").strip(),
        "breed": form.get("breed", "").strip(),
        "birth_date": form.get("birth_date", "").strip(),
        "sex": form.get("sex", "Не указан").strip() or "Не указан",
        "weight": form.get("weight", "").strip(),
        "color": form.get("color", "").strip(),
        "health_notes": form.get("health_notes", "").strip()
    }

    errors = []

    if not data["name"]:
        errors.append("Укажите кличку питомца.")

    if data["animal_type"] not in ANIMAL_TYPES:
        errors.append("Выберите вид животного.")

    if data["sex"] not in PET_SEX_OPTIONS:
        errors.append("Выберите пол животного.")

    if data["birth_date"]:
        try:
            birth = datetime.date.fromisoformat(data["birth_date"])
            if birth > datetime.date.today():
                errors.append("Дата рождения не может быть в будущем.")
        except ValueError:
            errors.append("Проверьте дату рождения.")

    weight_raw = data["weight"]
    weight_value = None

    if weight_raw:
        try:
            weight_value = float(weight_raw.replace(",", "."))
            if not 0 < weight_value <= 2000:
                errors.append("Проверьте значение веса.")
        except ValueError:
            errors.append("Вес должен быть указан числом.")

    if len(data["name"]) > 60:
        errors.append("Кличка слишком длинная.")

    if len(data["breed"]) > 80 or len(data["color"]) > 80:
        errors.append("Проверьте длину текста в полях породы и окраса.")

    if len(data["health_notes"]) > 1000:
        errors.append("Описание особенностей здоровья слишком длинное.")

    data["weight"] = weight_raw if errors else weight_value

    return data, errors


# Добавление нового питомца
@account_bp.route("/pets/add", methods=["GET", "POST"])
@login_required
def add_pet():
    user = current_user()

    if request.method == "POST":
        pet, errors = validate_pet_form(request.form)

        if errors:
            for error in errors:
                flash(error, "error")

            return render_template(
                "pet_form.html",
                pet=pet,
                is_edit=False,
                animal_types=ANIMAL_TYPES,
                sex_options=PET_SEX_OPTIONS,
                today=datetime.date.today().isoformat()
            )

        with get_db() as db:
            db.execute(
                """
                INSERT INTO pets
                (user_id, name, animal_type, breed, birth_date,
                 sex, weight, color, health_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    pet["name"],
                    pet["animal_type"],
                    pet["breed"],
                    pet["birth_date"],
                    pet["sex"],
                    pet["weight"],
                    pet["color"],
                    pet["health_notes"]
                )
            )

        flash("Питомец успешно добавлен!", "success")
        return redirect(url_for("account.account_page"))

    return render_template(
        "pet_form.html",
        pet={},
        is_edit=False,
        animal_types=ANIMAL_TYPES,
        sex_options=PET_SEX_OPTIONS,
        today=datetime.date.today().isoformat()
    )


# Редактирование информации о питомце
@account_bp.route("/pets/<int:pet_id>/edit", methods=["GET", "POST"])
@login_required
def edit_pet(pet_id):
    user = current_user()

    with get_db() as db:
        pet = db.execute(
            "SELECT * FROM pets WHERE id = ? AND user_id = ?",
            (pet_id, user["id"])
        ).fetchone()

    if pet is None:
        abort(404)

    if request.method == "POST":
        pet_data, errors = validate_pet_form(request.form)

        if errors:
            for error in errors:
                flash(error, "error")

            return render_template(
                "pet_form.html",
                pet=pet_data,
                is_edit=True,
                pet_id=pet_id,
                animal_types=ANIMAL_TYPES,
                sex_options=PET_SEX_OPTIONS,
                today=datetime.date.today().isoformat()
            )

        with get_db() as db:
            db.execute(
                """
                UPDATE pets
                SET name = ?, animal_type = ?, breed = ?,
                    birth_date = ?, sex = ?, weight = ?,
                    color = ?, health_notes = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    pet_data["name"],
                    pet_data["animal_type"],
                    pet_data["breed"],
                    pet_data["birth_date"],
                    pet_data["sex"],
                    pet_data["weight"],
                    pet_data["color"],
                    pet_data["health_notes"],
                    pet_id,
                    user["id"]
                )
            )

        flash("Данные питомца обновлены!", "success")
        return redirect(url_for("account.account_page"))

    return render_template(
        "pet_form.html",
        pet=dict(pet),
        is_edit=True,
        pet_id=pet_id,
        animal_types=ANIMAL_TYPES,
        sex_options=PET_SEX_OPTIONS,
        today=datetime.date.today().isoformat()
    )


# Удаление питомца
@account_bp.route("/pets/<int:pet_id>/delete", methods=["POST"])
@login_required
def delete_pet(pet_id):
    user = current_user()

    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM pets WHERE id = ? AND user_id = ?",
            (pet_id, user["id"])
        )

        deleted = cursor.rowcount

    if not deleted:
        abort(404)

    flash("Питомец удалён из вашего профиля.", "success")

    return redirect(url_for("account.account_page"))
# Маршруты 
@account_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("account.account_page"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if len(name) < 2:
            errors.append("Укажите имя (минимум 2 символа).")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Укажите корректный e-mail.")
        if len(password) < 6:
            errors.append("Пароль должен быть не короче 6 символов.")
        if password != confirm:
            errors.append("Пароли не совпадают.")

        if not errors:
            with get_db() as db:
                exists = db.execute(
                    "SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
                if exists:
                    errors.append("Пользователь с таким e-mail уже зарегистрирован.")
                else:
                    db.execute(
                        "INSERT INTO users (name, email, password_hash, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (name, email,
                         generate_password_hash(password, method='pbkdf2:sha256'),
                         datetime.date.today().isoformat()))

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=request.form)

        flash("Аккаунт создан! Теперь войдите в кабинет.", "success")
        return redirect(url_for("account.login"))

    return render_template("register.html", form={})


@account_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("account.account_page"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session.permanent = True
            flash("С возвращением, {}!".format(user["name"]), "success")
            return redirect(url_for("account.account_page"))
        flash("Неверный e-mail или пароль.", "error")
    return render_template("login.html", form=request.form)


@account_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Вы вышли из кабинета.", "success")
    return redirect(url_for("account.login"))


@account_bp.route("/account")
@login_required
def account_page():
    user = current_user()
    with get_db() as db:
        visits = db.execute(
            "SELECT service, amount, visit_date FROM visits "
            "WHERE user_id = ? ORDER BY visit_date DESC, id DESC",
            (user["id"],)).fetchall()
        pets_rows = db.execute(
            "SELECT * FROM pets WHERE user_id = ? ORDER BY name COLLATE NOCASE, id",
            (user["id"],)
        ).fetchall()

        pets = []

        for row in pets_rows:
            pet = dict(row)
            pet["age_label"] = pet_age_label(pet["birth_date"])
            pets.append(pet)

        vac_rows = db.execute(
            "SELECT v.*, p.name AS pet_name FROM vaccinations v "
            "JOIN pets p ON p.id = v.pet_id "
            "WHERE p.user_id = ? "
            "ORDER BY v.next_date IS NULL, v.next_date",
            (user["id"],)).fetchall()

    reminders = []
    for row in vac_rows:
        v = dict(row)
        v["status"] = vaccination_status(v["next_date"])
        if v["status"]["code"] in ("soon", "overdue"):
            reminders.append(v)
    reminders.sort(key=lambda v: (
        v["status"]["code"] != "overdue",
        v["status"]["days_left"] if v["status"]["days_left"] is not None else 9999))

    total_visits = len(visits)
    points = user["points"]
    level = level_for(total_visits)
    nxt = next_level_for(total_visits)

    if nxt:
        span = nxt["min_visits"] - level["min_visits"]
        done = total_visits - level["min_visits"]
        progress_pct = round(done / span * 100) if span else 100
        nxt_data = {"name": nxt["name"], "discount": nxt["discount"],
                    "left": nxt["min_visits"] - total_visits}
    else:
        progress_pct = 100
        nxt_data = None

    return render_template(
        "account.html",
        user=user,
        card_number="HP-{:06d}".format(user["id"]),
        points=points,
        points_value=points * RUB_PER_POINT,
        discount=level["discount"],
        level_name=level["name"],
        level_slug=level["slug"],
        total_visits=total_visits,
        visits_word=visits_word(total_visits),
        next_level=nxt_data,
        progress_pct=progress_pct,
        visits=visits,
        pets=pets,
        reminders=reminders,
    )
# =====================================
# САМОСТОЯТЕЛЬНАЯ ОТМЕТКА ВИЗИТА
# =====================================

@account_bp.route("/visit/add", methods=["POST"])
@login_required
def add_visit():
    """Пользователь сам отмечает свой визит в клинике."""
    service = request.form.get("service", "").strip()
    amount_raw = request.form.get("amount", "").strip()
    date_raw = request.form.get("visit_date", "").strip()

    if not service:
        flash("Укажите услугу.", "error")
        return redirect(url_for("account.account_page"))

    try:
        amount = float(amount_raw.replace(",", ".")) if amount_raw else 0.0
        assert amount >= 0
    except Exception:
        flash("Сумма должна быть неотрицательным числом.", "error")
        return redirect(url_for("account.account_page"))

    visit_date = date_raw or datetime.date.today().isoformat()

    user = current_user()
    with get_db() as db:
        db.execute(
            "INSERT INTO visits (user_id, service, amount, visit_date) "
            "VALUES (?, ?, ?, ?)",
            (user["id"], service, amount, visit_date))
        db.execute(
            "UPDATE users SET points = points + ? WHERE id = ?",
            (POINTS_PER_VISIT, user["id"]))

    flash("Визит отмечен: {} (+{} баллов)".format(
        service, POINTS_PER_VISIT), "success")
    return redirect(url_for("account.account_page"))
# =====================================
# ДНЕВНИК НАБЛЮДЕНИЯ ЗА ПИТОМЦЕМ
# =====================================

@account_bp.route("/pets/<int:pet_id>/diary", methods=["GET", "POST"])
@login_required
def pet_diary(pet_id):

    user = current_user()
    today = datetime.date.today().isoformat()

    with get_db() as db:

        # Проверяем, принадлежит ли питомец пользователю
        pet = db.execute(
            """
            SELECT * FROM pets
            WHERE id = ? AND user_id = ?
            """,
            (pet_id, user["id"])
        ).fetchone()

        if pet is None:
            abort(404)

        if request.method == "POST":

            # Получаем выбранные показатели
            appetite = request.form.get("appetite", "Обычный")
            activity = request.form.get("activity", "Обычная")
            wellbeing = request.form.get("wellbeing", "Хорошее")
            water_intake = request.form.get(
                "water_intake", "Обычное"
            )

            # Проверяем допустимые значения
            if appetite not in ("Слабый", "Обычный", "Хороший"):
                flash("Проверьте выбранный аппетит.", "error")
                return redirect(url_for(
                    "account.pet_diary", pet_id=pet_id
                ))

            if activity not in ("Низкая", "Обычная", "Высокая"):
                flash("Проверьте уровень активности.", "error")
                return redirect(url_for(
                    "account.pet_diary", pet_id=pet_id
                ))

            if wellbeing not in (
                "Хорошее", "Обычное", "Есть изменения"
            ):
                flash("Проверьте состояние питомца.", "error")
                return redirect(url_for(
                    "account.pet_diary", pet_id=pet_id
                ))

            if water_intake not in (
                "Меньше обычного", "Обычное", "Больше обычного"
            ):
                flash("Проверьте потребление воды.", "error")
                return redirect(url_for(
                    "account.pet_diary", pet_id=pet_id
                ))

            # Считываем отметки
            walked = 1 if request.form.get("walked") == "1" else 0
            played = 1 if request.form.get("played") == "1" else 0

            medication_given = (
                1 if request.form.get("medication_given") == "1"
                else 0
            )

            # Сохраняем наблюдение.
            # Если запись за сегодня уже существует,
            # обновляем её.
            db.execute(
                """
                INSERT INTO pet_health_log (
                    pet_id,
                    entry_date,
                    appetite,
                    activity,
                    wellbeing,
                    water_intake,
                    walked,
                    played,
                    medication_given
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(pet_id, entry_date)
                DO UPDATE SET
                    appetite = excluded.appetite,
                    activity = excluded.activity,
                    wellbeing = excluded.wellbeing,
                    water_intake = excluded.water_intake,
                    walked = excluded.walked,
                    played = excluded.played,
                    medication_given = excluded.medication_given
                """,
                (
                    pet_id,
                    today,
                    appetite,
                    activity,
                    wellbeing,
                    water_intake,
                    walked,
                    played,
                    medication_given
                )
            )

            flash("Наблюдение успешно сохранено!", "success")

            return redirect(url_for(
                "account.pet_diary",
                pet_id=pet_id
            ))

        # Получаем сегодняшнюю запись
        today_entry = db.execute(
            """
            SELECT * FROM pet_health_log
            WHERE pet_id = ? AND entry_date = ?
            """,
            (pet_id, today)
        ).fetchone()

        # Получаем историю наблюдений
        history = db.execute(
            """
            SELECT * FROM pet_health_log
            WHERE pet_id = ?
            ORDER BY entry_date DESC
            LIMIT 30
            """,
            (pet_id,)
        ).fetchall()

    return render_template(
        "pet_diary.html",
        pet=pet,
        today_entry=dict(today_entry) if today_entry else {},
        history=history,
        today=today
    )
# =====================================
# ПРИВИВКИ И ОБРАБОТКИ ПИТОМЦА
# =====================================

@account_bp.route("/pets/<int:pet_id>/vaccinations", methods=["GET", "POST"])
@login_required
def pet_vaccinations(pet_id):
    user = current_user()

    with get_db() as db:
        pet = db.execute(
            "SELECT * FROM pets WHERE id = ? AND user_id = ?",
            (pet_id, user["id"])).fetchone()
        if pet is None:
            abort(404)

        if request.method == "POST":
            name = request.form.get("vaccine_name", "").strip()
            date_done = request.form.get("date_done", "").strip()
            next_date = request.form.get("next_date", "").strip()
            notes = request.form.get("notes", "").strip()

            errors = []
            if not name:
                errors.append("Укажите название вакцины или процедуры.")
            if date_done:
                try:
                    d = datetime.date.fromisoformat(date_done)
                    if d > datetime.date.today():
                        errors.append("Дата процедуры не может быть в будущем.")
                except ValueError:
                    errors.append("Проверьте дату процедуры.")
            else:
                date_done = datetime.date.today().isoformat()
            if next_date:
                try:
                    datetime.date.fromisoformat(next_date)
                except ValueError:
                    errors.append("Проверьте дату следующей процедуры.")

            if errors:
                for e in errors:
                    flash(e, "error")
            else:
                db.execute(
                    "INSERT INTO vaccinations "
                    "(pet_id, vaccine_name, date_done, next_date, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (pet_id, name, date_done, next_date or None, notes or None))
                flash("Прививка добавлена!", "success")
                return redirect(url_for("account.pet_vaccinations", pet_id=pet_id))

        rows = db.execute(
            "SELECT * FROM vaccinations WHERE pet_id = ? "
            "ORDER BY date_done DESC, id DESC",
            (pet_id,)).fetchall()

    vaccinations = []
    for row in rows:
        v = dict(row)
        v["status"] = vaccination_status(v["next_date"])
        vaccinations.append(v)

    return render_template(
        "pet_vaccinations.html", pet=pet, vaccinations=vaccinations)


@account_bp.route("/vaccinations/<int:vac_id>/delete", methods=["POST"])
@login_required
def delete_vaccination(vac_id):
    user = current_user()
    with get_db() as db:
        row = db.execute(
            "SELECT v.pet_id FROM vaccinations v "
            "JOIN pets p ON p.id = v.pet_id "
            "WHERE v.id = ? AND p.user_id = ?",
            (vac_id, user["id"])).fetchone()
        if row is None:
            abort(404)
        pet_id = row["pet_id"]
        db.execute("DELETE FROM vaccinations WHERE id = ?", (vac_id,))

    flash("Запись о прививке удалена.", "success")
    return redirect(url_for("account.pet_vaccinations", pet_id=pet_id))

@account_bp.route("/admin-mark", methods=["GET", "POST"])
def admin_mark():
    if request.method == "POST":
        code = request.form.get("admin_code", "").strip()
        email = request.form.get("email", "").strip().lower()
        service = request.form.get("service", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        date_raw = request.form.get("visit_date", "").strip()

        if code != ADMIN_CODE:
            flash("Неверный код администратора.", "error")
            return render_template("admin_mark.html", form=request.form)
        if not service or not amount_raw:
            flash("Укажите услугу и сумму.", "error")
            return render_template("admin_mark.html", form=request.form)
        try:
            amount = float(amount_raw.replace(",", "."))
            assert amount >= 0
        except Exception:
            flash("Сумма должна быть неотрицательным числом.", "error")
            return render_template("admin_mark.html", form=request.form)
        visit_date = date_raw or datetime.date.today().isoformat()

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                flash("Клиент с таким e-mail не найден — пусть зарегистрируется.", "error")
                return render_template("admin_mark.html", form=request.form)
            db.execute(
                "INSERT INTO visits (user_id, service, amount, visit_date) "
                "VALUES (?, ?, ?, ?)",
                (user["id"], service, amount, visit_date))
            db.execute(
                "UPDATE users SET points = points + ? WHERE id = ?",
                (POINTS_PER_VISIT, user["id"]))

        flash("Визит отмечен: {} — {} (+{} баллов)".format(
            user["name"], service, POINTS_PER_VISIT), "success")
        return redirect(url_for("account.admin_mark"))

    return render_template("admin_mark.html", form={})
