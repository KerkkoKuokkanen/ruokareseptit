
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"  # needed for session

def init_db():
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # Recipes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                instructions TEXT NOT NULL,
                category TEXT NOT NULL
            )
        ''')
        conn.commit()

@app.route("/")
def redirect_to_main():
    return redirect(url_for("main_page"))

@app.route("/main", methods=["GET", "POST"])
def main_page():
    search_term = request.args.get("search", "")  # get search term from query params

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        if search_term:
            cursor.execute("""
                SELECT username, title, instructions, category
                FROM recipes
                WHERE title LIKE ?
                ORDER BY id DESC
            """, ('%' + search_term + '%',))
        else:
            cursor.execute("""
                SELECT username, title, instructions, category
                FROM recipes
                ORDER BY id DESC
                LIMIT 10
            """)
        recent_recipes = cursor.fetchall()

    return render_template("main.html", recent_recipes=recent_recipes, username=session.get("username"), search_term=search_term)


@app.route("/home", methods=["GET", "POST"])
def home():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        instructions = request.form["instructions"]
        category = request.form["category"]
        username = session["username"]

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO recipes (username, title, instructions, category) VALUES (?, ?, ?, ?)",
                (username, title, instructions, category)
            )
            conn.commit()

        return redirect(url_for("home"))

    # Fetch all recipes by this user
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, instructions, category FROM recipes WHERE username = ?", (session["username"],))
        recipes = cursor.fetchall()

    return render_template("home.html", username=session["username"], recipes=recipes)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        try:
            with sqlite3.connect("database.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already taken. Please choose another."

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()

            if user:
                session["username"] = username
                return redirect(url_for("home"))
            else:
                return "Invalid credentials."

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete(recipe_id):
    if "username" not in session:
        return redirect(url_for("login"))

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recipes WHERE id = ? AND username = ?", (recipe_id, session["username"]))
        conn.commit()

    return redirect(url_for("home"))

@app.route("/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit(recipe_id):
    if "username" not in session:
        return redirect(url_for("login"))

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()

        if request.method == "POST":
            title = request.form["title"]
            instructions = request.form["instructions"]
            category = request.form["category"]

            cursor.execute("""
                UPDATE recipes
                SET title = ?, instructions = ?, category = ?
                WHERE id = ? AND username = ?
            """, (title, instructions, category, recipe_id, session["username"]))
            conn.commit()

            return redirect(url_for("home"))

        # GET: load recipe to edit
        cursor.execute("SELECT title, instructions, category FROM recipes WHERE id = ? AND username = ?", (recipe_id, session["username"]))
        recipe = cursor.fetchone()

        if recipe:
            return render_template("edit.html", recipe_id=recipe_id, recipe=recipe)
        else:
            return "Recipe not found."

if __name__ == "__main__":
    init_db()
    app.run(debug=True)

