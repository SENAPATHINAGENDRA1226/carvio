from flask import Flask, render_template, request, redirect, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2, psycopg2.extras
import json, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO

app = Flask(__name__)
app.secret_key = "carvia-secret-key"

# ================= DATABASE =================

def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )

# ================= LOGIN =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user is None:
            flash("Email not registered. Please sign up.")
            return redirect("/")

        if not check_password_hash(user["password"], password):
            flash("Incorrect password.")
            return redirect("/")

        session["user"] = user["id"]
        return redirect("/onboarding")

    return render_template("login.html")

# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match.")
            return redirect("/register")

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Email already exists.")
            return redirect("/register")

        hashed = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING id",
            (name, email, hashed)
        )
        user_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO profile (user_id, role, skills) VALUES (%s, %s, %s)",
            (user_id, None, None)
        )

        db.commit()
        flash("Registration successful. Please login.")
        return redirect("/")

    return render_template("register.html")

# ================= FORGOT PASSWORD =================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email not registered.")
            return redirect("/forgot-password")

        session["reset_user"] = user[0]
        return redirect("/reset-password")

    return render_template("forgot_password.html")

# ================= RESET PASSWORD =================

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_user" not in session:
        return redirect("/")

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match.")
            return redirect("/reset-password")

        db = get_db()
        cur = db.cursor()
        hashed = generate_password_hash(password)

        cur.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (hashed, session["reset_user"])
        )
        db.commit()
        session.pop("reset_user")
        flash("Password reset successful.")
        return redirect("/")

    return render_template("reset_password.html")

# ================= ONBOARDING =================

@app.route("/onboarding")
def onboarding():
    if "user" not in session:
        return redirect("/")
    return render_template("onboarding.html")

# ================= SKILLS =================

@app.route("/skills", methods=["GET", "POST"])
def skills():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        skills = request.form.get("skills")
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "UPDATE profile SET skills=%s WHERE user_id=%s",
            (skills, session["user"])
        )
        db.commit()
        return redirect("/roles")

    return render_template("skills.html")

# ================= ROLES =================

@app.route("/roles", methods=["GET", "POST"])
def roles():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        role = request.form.get("role")
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "UPDATE profile SET role=%s WHERE user_id=%s",
            (role, session["user"])
        )
        db.commit()
        return redirect("/roadmap")

    return render_template("role_select.html")

# ================= ROADMAP =================

ROLE_SKILLS = {
    "Frontend Engineer": ["HTML", "CSS", "JavaScript"],
    "Backend Developer": ["Python", "Java", "C"],
    "Full-Stack Web Developer": ["HTML", "CSS", "JavaScript", "Python", "Java"],
    "Software Development Engineer (SDE)": ["Java", "Python", "C"],
    "Data Analyst / Junior Data Scientist": ["Python"],
    "Android App Developer": ["Java"],
    "Embedded Systems Engineer": ["C"],
    "Automation / QA Engineer": ["Python", "JavaScript"],
    "Product Designer (UI/UX)": ["UI/UX"],
    "Cyber Security Analyst": ["C", "Python"]
}

@app.route("/roadmap")
def roadmap():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT role FROM profile WHERE user_id=%s", (session["user"],))
    role = cur.fetchone()[0]

    skills = ROLE_SKILLS.get(role, [])
    return render_template("roadmap.html", role=role, skills=skills)

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT name FROM users WHERE id=%s", (session["user"],))
    user = cur.fetchone()

    cur.execute("SELECT role, skills FROM profile WHERE user_id=%s", (session["user"],))
    profile = cur.fetchone()

    user_skills = json.loads(profile["skills"]) if profile["skills"] else []
    roadmap_skills = ROLE_SKILLS.get(profile["role"], [])

    return render_template(
        "dashboard.html",
        name=user["name"],
        role=profile["role"],
        user_skills=user_skills,
        roadmap_skills=roadmap_skills
    )

# ================= DOWNLOAD ROADMAP PDF =================

SKILL_IMAGES = {
    "HTML": "html(rm).jpeg",
    "CSS": "css(rm).jpeg",
    "JavaScript": "js(rm).jpeg",
    "Python": "python (rm).jpeg",
    "Java": "java(rm).jpeg",
    "C": "c(rm).jpeg",
    "UI/UX": "ui(rm).jpeg"
}

@app.route("/download-roadmap")
def download_roadmap():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT role FROM profile WHERE user_id=%s", (session["user"],))
    role = cur.fetchone()[0]

    skills = ROLE_SKILLS.get(role, [])

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, h - 60, "Roadmap by Carvia")
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h - 95, role)
    c.showPage()

    for skill in skills:
        img = SKILL_IMAGES.get(skill)
        if not img:
            continue

        path = os.path.join(app.root_path, "static", "roadmaps", img)
        if not os.path.exists(path):
            continue

        image = ImageReader(path)
        iw, ih = image.getSize()
        scale = min((w - 100) / iw, (h - 100) / ih)
        c.drawImage(
            image,
            (w - iw * scale) / 2,
            (h - ih * scale) / 2,
            iw * scale,
            ih * scale
        )
        c.showPage()

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{role.replace(' ', '_')}_roadmap.pdf",
        mimetype="application/pdf"
    )

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
