from flask import Flask, render_template, request, redirect, url_for
from database import init_db
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
    return render_template("services.html")


@app.route("/specialists")
def specialists():
    return render_template("specialists.html")


@app.route("/appointment")
def appointment():
    return render_template("appointment.html")


@app.route("/contacts")
def contacts():
    return render_template("contacts.html")


# --- Твоя часть: работа с клиентами ---

@app.route("/add_client", methods=["POST"])
def add_client_route():
    """Обработка формы записи."""
    pet_name = request.form.get("pet_name")
    pet_type = request.form.get("pet_type")
    owner_name = request.form.get("owner_name")
    phone = request.form.get("phone")
    reason = request.form.get("reason", "")
    preferred_time = request.form.get("preferred_time", "")

    if pet_name and owner_name and phone:
        add_client(pet_name, pet_type, owner_name, phone, reason, preferred_time)

    return redirect(url_for("admin_clients"))


@app.route("/admin/clients")
def admin_clients():
    """Страница со списком всех клиентов."""
    clients = get_all_clients()
    return render_template("admin_clients.html", clients=clients)


if __name__ == "__main__":
    app.run(debug=True)