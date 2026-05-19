from flask import Flask, render_template, request, redirect, session, jsonify, Response
import sqlite3
import datetime
import uuid
import cv2
import firebase_admin
from firebase_admin import credentials, db

from detector_yolov8 import (
    classify_frame,
    start_camera as start_cam,
    stop_camera as stop_cam,
    get_frame
)

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ----------------------------------------------------
# FIREBASE INIT
# ----------------------------------------------------
cred = credentials.Certificate("firebase-admin.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://binlevel-bd0a6-default-rtdb.firebaseio.com/"
    })

# ----------------------------------------------------
# SQLITE INIT
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT,
            category TEXT,
            confidence REAL,
            timestamp TEXT,
            user TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------
# AUTH
# ----------------------------------------------------
@app.route("/")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/do_register", methods=["POST"])
def do_register():
    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]
    role = request.form["role"]

    try:
        conn = sqlite3.connect("users.db")
        conn.execute(
            "INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)",
            (name, email, password, role)
        )
        conn.commit()
    except:
        return "Email already exists!"

    return redirect("/")

@app.route("/do_login", methods=["POST"])
def do_login():
    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    user = cur.fetchone()

    if not user:
        return "Invalid Credentials!"

    session["user"] = user[1]
    session["role"] = user[4]

    return redirect("/admin" if user[4] == "admin" else "/user")

# ----------------------------------------------------
# DASHBOARD
# ----------------------------------------------------
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")

@app.route("/user")
def user_dashboard():
    if session.get("role") != "user":
        return redirect("/")
    return render_template("user_dashboard.html")

# ----------------------------------------------------
# CAMERA CONTROL
# ----------------------------------------------------
@app.route("/start_camera")
def start_camera():
    start_cam()
    return "started"

@app.route("/stop_camera")
def stop_camera():
    stop_cam()
    return "stopped"

# ----------------------------------------------------
# LIVE STREAM
# ----------------------------------------------------
def generate_stream():
    while True:
        frame = get_frame()
        if frame:
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                frame + b"\r\n"
            )

@app.route("/video_feed")
def video_feed():
    return Response(generate_stream(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# ----------------------------------------------------
# CAPTURE & DETECT
# ----------------------------------------------------
@app.route("/capture_detect")
def capture_detect():
    frame = get_frame()

    if frame is None:
        return jsonify({"error": "No frame"}), 500

    filename = f"static/uploads/{uuid.uuid4()}.jpg"
    with open(filename, "wb") as f:
        f.write(frame)

    img = cv2.imread(filename)
    label, conf = classify_frame(img)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("users.db")
    conn.execute("""
        INSERT INTO history(image, category, confidence, timestamp, user)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, label, conf, ts, session.get("user", "admin")))
    conn.commit()

    db.reference("/SMARTBIN/DETECTION").set(label)

    return jsonify({
        "image": filename,
        "category": label,
        "confidence": conf
    })

# ----------------------------------------------------
# UPLOAD DETECT
# ----------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["image"]
    filename = f"static/uploads/{uuid.uuid4()}.jpg"
    file.save(filename)

    img = cv2.imread(filename)
    label, conf = classify_frame(img)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("users.db")
    conn.execute("""
        INSERT INTO history(image, category, confidence, timestamp, user)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, label, conf, ts, session["user"]))
    conn.commit()

    db.reference("/SMARTBIN/DETECTION").set(label)

    return jsonify({
        "image": filename,
        "category": label,
        "confidence": conf
    })

# ----------------------------------------------------
# USER HISTORY
# ----------------------------------------------------
@app.route("/history")
def history():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT image, category, confidence, timestamp
        FROM history
        WHERE user=?
    """, (session["user"],))

    rows = cur.fetchall()

    return jsonify([
        {"image": r[0], "category": r[1], "confidence": r[2], "timestamp": r[3]}
        for r in rows
    ])

# ----------------------------------------------------
# BIN LIVE
# ----------------------------------------------------
@app.route("/api/bin")
def api_bin():
    return jsonify(db.reference("/SMARTBIN/LIVE").get())

# ----------------------------------------------------
# BIN HISTORY
# ----------------------------------------------------
@app.route("/api/bin_history")
def api_bin_history():
    data = db.reference("/SMARTBIN/DATABASE").get()
    history = []

    if data:
        for ts, entry in data.items():
            if not ts.isdigit():
                continue

            history.append({
                "timestamp": datetime.datetime.fromtimestamp(int(ts)).strftime("%H:%M:%S"),
                "bin1": entry.get("BIN1", 0),
                "bin2": entry.get("BIN2", 0)
            })

    return jsonify(history)

# ----------------------------------------------------
# RESET DATA
# ----------------------------------------------------
@app.route("/reset_data")
def reset_data():
    try:
        # 1. Reset SQLite history
        conn = sqlite3.connect("users.db")
        conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()

        # 2. Reset Firebase Live levels (to 0)
        db.reference("/SMARTBIN/LIVE").set({"BIN1": 0, "BIN2": 0})

        # 3. Clear Firebase History
        db.reference("/SMARTBIN/DATABASE").delete()

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ----------------------------------------------------
# LOGOUT
# ----------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ----------------------------------------------------
# RUN
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)