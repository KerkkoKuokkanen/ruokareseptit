
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import secrets

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id),
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        conn.commit()

@app.route("/")
def redirect_to_main():
    return redirect(url_for("main_page"))

@app.route("/main", methods=["GET", "POST"])
def main_page():
    search_term = request.args.get("search", "")
    selected_category = request.args.get("category", "any")
    username = session.get("username")

    if request.method == "POST" and username:
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Invalid CSRF token", 403
        recipe_id = request.form["recipe_id"]
        rating = int(request.form["rating"])
        comment = request.form["comment"][:120]

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ratings (recipe_id, username, rating, comment)
                VALUES (?, ?, ?, ?)
            """, (recipe_id, username, rating, comment))
            conn.commit()

        return redirect(url_for("main_page", search=search_term, category=selected_category))

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()

        # Build query dynamically
        if selected_category != "any":
            cursor.execute("""
                SELECT id, username, title, instructions, category
                FROM recipes
                WHERE title LIKE ? AND category = ?
                ORDER BY id DESC
            """, ('%' + search_term + '%', selected_category))
        else:
            cursor.execute("""
                SELECT id, username, title, instructions, category
                FROM recipes
                WHERE title LIKE ?
                ORDER BY id DESC
            """, ('%' + search_term + '%',))

        recent_recipes = cursor.fetchall()

        # Load ratings
        ratings_data = {}
        for recipe in recent_recipes:
            recipe_id = recipe[0]
            cursor.execute("SELECT AVG(rating), COUNT(*) FROM ratings WHERE recipe_id = ?", (recipe_id,))
            avg_rating, count = cursor.fetchone()
            cursor.execute("SELECT username, rating, comment FROM ratings WHERE recipe_id = ? ORDER BY id DESC LIMIT 3", (recipe_id,))
            comments = cursor.fetchall()
            ratings_data[recipe_id] = {
                "avg": round(avg_rating, 1) if avg_rating else None,
                "count": count,
                "comments": comments
            }

    return render_template("main.html", recent_recipes=recent_recipes, username=username, search_term=search_term, ratings_data=ratings_data, csrf_token=get_csrf_token(), selected_category=selected_category)



@app.route("/home", methods=["GET", "POST"])
def home():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Invalid CSRF token", 403
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

    # Fetch user's recipes
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, instructions, category FROM recipes WHERE username = ?", (session["username"],))
        recipes = cursor.fetchall()

        # Fetch ratings for each recipe
        ratings_data = {}
        for recipe in recipes:
            recipe_id = recipe[0]
            cursor.execute("SELECT AVG(rating), COUNT(*) FROM ratings WHERE recipe_id = ?", (recipe_id,))
            avg_rating, count = cursor.fetchone()
            cursor.execute("SELECT username, rating, comment FROM ratings WHERE recipe_id = ? ORDER BY id DESC LIMIT 3", (recipe_id,))
            comments = cursor.fetchall()
            ratings_data[recipe_id] = {
                "avg": round(avg_rating, 1) if avg_rating else None,
                "count": count,
                "comments": comments
            }

    return render_template("home.html", username=session["username"], recipes=recipes, ratings_data=ratings_data, csrf_token=get_csrf_token())

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Invalid CSRF token", 403
        username = request.form["username"]
        password = request.form["password"]

        if len(password) < 8:
            error = "Password must be at least 8 characters long."
        else:
            try:
                with sqlite3.connect("database.db") as conn:
                    cursor = conn.cursor()
                    hashed_password = hash_password(password)
                    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                    conn.commit()
                    return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                error = "Username already taken. Please choose another."

    return render_template("register.html", error=error, csrf_token=get_csrf_token())



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Invalid CSRF token", 403
        username = request.form["username"]
        password = request.form["password"]

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            hashed_password = hash_password(password)
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
            user = cursor.fetchone()

            if user:
                session["username"] = username
                return redirect(url_for("home"))
            else:
                return "Invalid credentials."

    return render_template("login.html", csrf_token=get_csrf_token())

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("main_page"))

@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete(recipe_id):
    if "username" not in session:
        return redirect(url_for("login"))

    if request.form.get("csrf_token") != session.get("csrf_token"):
        return "Invalid CSRF token", 403

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recipes WHERE id = ? AND username = ?", (recipe_id, session["username"]))
        conn.commit()

    return redirect(url_for("home"))

@app.route("/profile/<username>")
def profile(username):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        
        # 1. Fetch recipes sorted by the number of reviews (Highest first)
        # We use LEFT JOIN so recipes with 0 reviews still show up
        cursor.execute("""
            SELECT r.id, r.title, r.instructions, r.category, COUNT(ra.id) as review_count, AVG(ra.rating)
            FROM recipes r
            LEFT JOIN ratings ra ON r.id = ra.recipe_id
            WHERE r.username = ?
            GROUP BY r.id
            ORDER BY review_count DESC
        """, (username,))
        
        user_recipes = cursor.fetchall()

        # 2. Get global stats (Average and Total count)
        cursor.execute("""
            SELECT AVG(ra.rating), COUNT(ra.id)
            FROM ratings ra
            JOIN recipes r ON ra.recipe_id = r.id 
            WHERE r.username = ?
        """, (username,))
        
        avg_result, total_reviews = cursor.fetchone()
        overall_avg = round(avg_result, 1) if avg_result else "No ratings yet"

    return render_template("profile.html", 
                           profile_user=username, 
                           recipes=user_recipes, 
                           overall_avg=overall_avg, 
                           total_reviews=total_reviews)

@app.route("/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit(recipe_id):
    if "username" not in session:
        return redirect(url_for("login"))

    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()

        if request.method == "POST":
            if request.form.get("csrf_token") != session.get("csrf_token"):
                return "Invalid CSRF token", 403

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
            return render_template("edit.html", recipe_id=recipe_id, recipe=recipe, csrf_token=get_csrf_token())
        else:
            return "Recipe not found."

if __name__ == "__main__":
    init_db()
    app.run(debug=True)

