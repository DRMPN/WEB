import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, abort

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")

@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        # Delete birthday entries
        if "delete_birthday" in request.form:
            birthday_id = request.form.get("birthday_id")
            db.execute("DELETE FROM birthdays WHERE id=?", birthday_id)
            print("Deleted")
            return redirect("/")

        name = request.form.get("name")
        month = request.form.get("month")
        day = request.form.get("day")

        # Check for empty fields:
        if not name or not month or not day:
            # TODO: note the error to user
            return redirect("/", code=304)
        else:
            # Add the user's entry into the database
            db.execute("INSERT INTO birthdays (name, month, day) VALUES (?, ?, ?)", name, month, day)
            return redirect("/")

    else:
        # Display the entries in the database on index.html
        birthdays = db.execute("SELECT * FROM birthdays")
        return render_template("index.html", birthdays=birthdays)