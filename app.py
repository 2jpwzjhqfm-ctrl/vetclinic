
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request

app = Flask(
    __name__,
    template_folder="pages",
    static_folder=".",
    static_url_path=""
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/services")
def services():
    db_path = Path(__file__).resolve().parent / "clinic.db"

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        services_from_db = connection.execute("""
            SELECT id, name, description, price,
                   duration_minutes, category, image
            FROM services
            WHERE is_active = 1
            ORDER BY id
        """).fetchall()

    return render_template(
        "services.html",
        services=services_from_db
    )


@app.route("/services/<int:service_id>")
def service_detail(service_id):
    db_path = Path(__file__).resolve().parent / "clinic.db"

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        service = connection.execute("""
            SELECT id, name, description, price,
                   duration_minutes, category, image
            FROM services
            WHERE id = ? AND is_active = 1
        """, (service_id,)).fetchone()

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

    if service_id is not None:
        db_path = Path(__file__).resolve().parent / "clinic.db"

        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row

            selected_service = connection.execute("""
                SELECT id, name, description, price,
                       duration_minutes, category, image
                FROM services
                WHERE id = ? AND is_active = 1
            """, (service_id,)).fetchone()

    return render_template(
        "appointment.html",
        selected_service=selected_service
    )


@app.route("/contacts")
def contacts():
    return render_template("contacts.html")


if __name__ == "__main__":
    app.run(debug=True)
