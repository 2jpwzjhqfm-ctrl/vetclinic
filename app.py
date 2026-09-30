from flask import Flask, render_template

app = Flask(__name__, template_folder="pages")


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


if __name__ == "__main__":
    app.run(debug=True)
