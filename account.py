import os
import sqlite3
import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, send_from_directory
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
        """)


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
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
    )


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
