from flask import Flask, render_template, request, redirect, url_for
from database import init_db, get_connection
from models import add_client, get_all_clients

app = Flask(
    __name__,
    template_folder="pages",
    static_folder=".",
    static_url_path=""
)

# Инициализация базы данных при запуске
init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/services")
def services():
    """Показывает список услуг из базы данных."""
    conn = get_connection()
    conn.row_factory = lambda cursor, row: {
        column[0]: row[index]
        for index, column in enumerate(cursor.description)
    }

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
    conn = get_connection()
    conn.row_factory = lambda cursor, row: {
        column[0]: row[index]
        for index, column in enumerate(cursor.description)
    }

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

    if service_id is not None:
        conn = get_connection()
        conn.row_factory = lambda cursor, row: {
            column[0]: row[index]
            for index, column in enumerate(cursor.description)
        }

        selected_service = conn.execute("""
            SELECT id, name, description, price,
                   duration_minutes, category, image
            FROM services
            WHERE id = ? AND is_active = 1
        """, (service_id,)).fetchone()

        conn.close()

    return render_template(
        "appointment.html",
        selected_service=selected_service
    )


@app.route("/contacts")
def contacts():
    return render_template("contacts.html")


@app.route("/add_client", methods=["POST"])
def add_client_route():
    """Обрабатывает форму записи на приём."""
    pet_name = request.form.get("pet_name")
    pet_type = request.form.get("pet_type")
    owner_name = request.form.get("owner_name")
    phone = request.form.get("phone")
    reason = request.form.get("reason", "")
    preferred_time = request.form.get("preferred_time", "")

    if pet_name and owner_name and phone:
        add_client(
            pet_name,
            pet_type,
            owner_name,
            phone,
            reason,
            preferred_time
        )

    return redirect(url_for("admin_clients"))


@app.route("/admin/clients")
def admin_clients():
    """Показывает список всех клиентов."""
    clients = get_all_clients()
    return render_template(
        "admin_clients.html",
        clients=clients
    )


if __name__ == "__main__":
    app.run(debug=True)