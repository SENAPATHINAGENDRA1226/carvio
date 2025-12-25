from flask import Flask, render_template, request, redirect, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, json, os, tempfile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PIL import Image
from reportlab.lib.utils import ImageReader
from io import BytesIO

app = Flask(__name__)
app.secret_key = "carvia-secret-key"

# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        # ❌ Email not registered
        if user is None:
            flash("Email not registered with us. Please Signup"
            ".")
            return redirect("/")

        # ❌ Password incorrect
        if not check_password_hash(user["password"], password):
            flash("Incorrect password.")
            return redirect("/")

        # ✅ Login success
        session["user"] = user["id"]
        return redirect("/onboarding")

    return render_template("login.html")



#=================Forgot Password===============

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if user is None:
            flash("Email not registered with us.")
            return redirect("/forgot-password")

        session["reset_user"] = user["id"]
        return redirect("/reset-password")

    return render_template("forgot_password.html")

#=================Reset Password===============

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
        hashed = generate_password_hash(password)

        db.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hashed, session["reset_user"])
        )
        db.commit()

        session.pop("reset_user")
        flash("Password reset successful. Please login.")
        return redirect("/")

    return render_template("reset_password.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match")
            return redirect("/register")

        db = get_db()
        if db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone():
            flash("Email already exists")
            return redirect("/register")

        cursor = db.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password))
        )

        db.execute(
            "INSERT INTO profile (user_id, role, skills) VALUES (?, ?, ?)",
            (cursor.lastrowid, None, None)
        )

        db.commit()
        flash("Registration successful. Please login.")
        return redirect("/")

    return render_template("register.html")

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
        db = get_db()
        db.execute(
            "UPDATE profile SET skills=? WHERE user_id=?",
            (request.form.get("skills"), session["user"])
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
        db = get_db()
        db.execute(
            "UPDATE profile SET role=? WHERE user_id=?",
            (request.form.get("role"), session["user"])
        )
        db.commit()
        return redirect("/roadmap")

    return render_template("role_select.html")

# ================= ROADMAP =================

@app.route("/roadmap")
def roadmap():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    profile = db.execute(
        "SELECT role FROM profile WHERE user_id=?",
        (session["user"],)
    ).fetchone()

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

    role = profile["role"]
    skills = ROLE_SKILLS.get(role, [])

    return render_template("roadmap.html", role=role, skills=skills)
#================== DASHBOARD =============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()

    user = db.execute(
        "SELECT name FROM users WHERE id=?",
        (session["user"],)
    ).fetchone()

    profile = db.execute(
        "SELECT role, skills FROM profile WHERE user_id=?",
        (session["user"],)
    ).fetchone()

    db.close()

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

    role = profile["role"]
    roadmap_skills = ROLE_SKILLS.get(role, [])

    user_skills = []
    if profile["skills"]:
        try:
            user_skills = json.loads(profile["skills"])
        except:
            pass

    return render_template(
        "dashboard.html",
        name=user["name"],
        role=role,
        user_skills=user_skills,
        roadmap_skills=roadmap_skills
    )


# ================= DOWNLOAD ROADMAP (PDF) =================

from io import BytesIO

@app.route("/download-roadmap")
def download_roadmap():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    profile = db.execute(
        "SELECT role FROM profile WHERE user_id=?",
        (session["user"],)
    ).fetchone()

    if not profile or not profile["role"]:
        return redirect("/roadmap")

    role = profile["role"]

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

    SKILL_IMAGES = {
        "HTML": "html(rm).jpeg",
        "CSS": "css(rm).jpeg",
        "JavaScript": "js(rm).jpeg",
        "Python": "python (rm).jpeg",
        "Java": "java(rm).jpeg",
        "C": "c(rm).jpeg",
        "UI/UX": "ui(rm).jpeg"
    }

    skills = ROLE_SKILLS.get(role, [])

    # ✅ Create PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    # Cover page
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(page_width / 2, page_height - 60, "Roadmap by SkillPath")
    c.setFont("Helvetica", 14)
    c.drawCentredString(page_width / 2, page_height - 95, role)
    c.showPage()

    for skill in skills:
        img_name = SKILL_IMAGES.get(skill)
        if not img_name:
            continue

        img_path = os.path.join(app.root_path, "static", "roadmaps", img_name)
        if not os.path.exists(img_path):
            continue

        img = ImageReader(img_path)

        margin = 50
        max_w = page_width - 2 * margin
        max_h = page_height - 2 * margin

        iw, ih = img.getSize()
        scale = min(max_w / iw, max_h / ih)

        w = iw * scale
        h = ih * scale
        x = (page_width - w) / 2
        y = (page_height - h) / 2

        c.drawImage(img, x, y, width=w, height=h)
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

