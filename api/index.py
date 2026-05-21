import base64
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

API_DIR = Path(__file__).resolve().parent
BASE_DIR = API_DIR.parent
DB_PATH = BASE_DIR / "paws_without_homes.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
IMAGES_DIR = BASE_DIR / "images"
ANIMALS_FILE = BASE_DIR / "animals.json"
INDEX_HTML_PATH = BASE_DIR / "index.html"

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "paws-without-homes-dev-secret")
app.permanent_session_lifetime = timedelta(days=30)

ADMIN_PASSWORD = "admin123"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"

if ANIMALS_FILE.exists():
    with open(ANIMALS_FILE, "r", encoding="utf-8") as file:
        animals = json.load(file)
else:
    animals = []

adoptions = []
volunteers = []
reports = []
lost_found = []


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Database schema not found at {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_db_connection() as conn:
        conn.executescript(schema_sql)
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(donations)").fetchall()
        }
        if "payment_id" not in existing_columns:
            conn.execute("ALTER TABLE donations ADD COLUMN payment_id TEXT")
        if "razorpay_order_id" not in existing_columns:
            conn.execute("ALTER TABLE donations ADD COLUMN razorpay_order_id TEXT")
        conn.commit()


def validate_registration(name, email, password):
    if len(name.strip()) < 2:
        return "Please enter your full name."
    if not EMAIL_RE.match(email.strip().lower()):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    return None


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def wants_json_response():
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def unauthorized_response():
    if wants_json_response():
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return redirect(url_for("login_page"))


def donation_totals():
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS donations_count,
                COALESCE(SUM(amount), 0) AS total_amount
            FROM donations
            """
        ).fetchone()
    return {
        "donations_count": row["donations_count"],
        "total_amount": float(row["total_amount"]),
    }


def site_stats():
    totals = donation_totals()
    return {
        "total_cases": len(reports),
        "rescued": len(reports),
        "adopted": len(adoptions),
        "volunteers": len(volunteers),
        "total_donations": totals["total_amount"],
    }


def serialize_donation(row):
    return {
        "id": row["id"],
        "amount": float(row["amount"]),
        "date": row["donated_at"],
        "description": row["description"] or "",
        "campaign_name": row["campaign_name"] or "",
        "frequency": row["frequency"],
        "status": row["status"],
        "transaction_id": row["transaction_id"],
        "payment_id": row["payment_id"] if "payment_id" in row.keys() else None,
    }


def is_razorpay_configured():
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def razorpay_auth_header():
    token = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def create_razorpay_order(amount_paise, receipt, notes):
    payload = json.dumps(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
            "notes": notes,
        }
    ).encode("utf-8")
    req = urllib_request.Request(
        RAZORPAY_ORDERS_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **razorpay_auth_header(),
        },
    )
    with urllib_request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_razorpay_signature(order_id, payment_id, signature):
    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


@app.context_processor
def template_helpers():
    return {
        "format_inr": lambda amount: f"Rs. {float(amount or 0):,.2f}",
    }


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/login")
def login_page():
    if get_current_user():
        return redirect(url_for("index"))
    return render_template("login.html", next_url=request.args.get("next", "/"))


@app.route("/register")
def register_page():
    if get_current_user():
        return redirect(url_for("index"))
    return render_template("register.html", next_url=request.args.get("next", "/"))


@app.route("/contributions")
def contributions_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login_page", next="/contributions"))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, amount, donated_at, description, campaign_name, status, transaction_id
            FROM donations
            WHERE user_id = ?
            ORDER BY donated_at DESC
            """,
            (user["id"],),
        ).fetchall()

    donation_history = [
        {
            "id": row["id"],
            "purpose": row["campaign_name"] or row["description"] or "General Rescue Fund",
            "amount": float(row["amount"]),
            "status": row["status"],
            "transaction_id": row["transaction_id"],
            "date": datetime.fromisoformat(row["donated_at"]),
        }
        for row in rows
    ]

    return render_template(
        "my_donations.html",
        donation_history=donation_history,
        total_contribution=sum(item["amount"] for item in donation_history),
        donations_count=len(donation_history),
        display_name=user["name"],
    )


@app.route("/requirements")
def requirements_page():
    return render_template(
        "requirements.html",
        display_name=(get_current_user() or {}).get("name", "Supporter"),
    )


@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/register", methods=["POST"])
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    error = validate_registration(name, email, password)
    if error:
        return jsonify({"success": False, "message": error}), 400

    password_hash = generate_password_hash(password)

    try:
        with get_db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
            user_id = cur.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "An account with this email already exists."}), 409

    session["user_id"] = user_id
    session["user_name"] = name
    session.permanent = True
    return jsonify(
        {
            "success": True,
            "message": "Welcome to Paws Without Homes.",
            "user": {"id": user_id, "name": name, "email": email},
        }
    )


@app.route("/login", methods=["POST"])
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
    if not password:
        return jsonify({"success": False, "message": "Password is required."}), 400

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"success": False, "message": "Invalid email or password."}), 401

    session["user_id"] = row["id"]
    session["user_name"] = row["name"]
    session.permanent = True

    return jsonify(
        {
            "success": True,
            "message": f"Welcome back, {row['name']}.",
            "user": {"id": row["id"], "name": row["name"], "email": row["email"]},
        }
    )


@app.route("/logout", methods=["POST"])
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "You have been logged out."})


@app.route("/me")
@app.route("/user")
@app.route("/api/user")
def user():
    current_user = get_current_user()
    return jsonify(
        {
            "authenticated": bool(current_user),
            "user": current_user,
        }
    )


@app.route("/api/me")
def me_alias():
    return user()


@app.route("/api/donation-summary")
def donation_summary():
    return jsonify({"success": True, **donation_totals()})


@app.route("/api/site-stats")
def public_site_stats():
    return jsonify({"success": True, "data": site_stats()})


@app.route("/my-donations")
@app.route("/api/my-donations")
@app.route("/donations")
@app.route("/api/donations")
def get_user_donations():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Please sign in to view your donations."}), 401

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, amount, donated_at, description, campaign_name, frequency, status, transaction_id, payment_id
            FROM donations
            WHERE user_id = ?
            ORDER BY donated_at DESC
            """,
            (current_user["id"],),
        ).fetchall()

    records = [serialize_donation(row) for row in rows]
    return jsonify(
        {
            "success": True,
            "donations": records,
            "total_contribution": round(sum(item["amount"] for item in records), 2),
        }
    )


@app.route("/api/animals")
def get_animals():
    return jsonify({"success": True, "data": animals})


@app.route("/api/report", methods=["POST"])
def report():
    data = request.get_json(silent=True) or {}
    case_id = f"PAW{random.randint(1000, 9999)}"
    reports.append({"id": case_id, **data, "status": "Reported", "timeline": [{"status": "Reported", "time": "Now"}]})
    return jsonify({"success": True, "message": f"Report submitted! Case ID: {case_id}"})


@app.route("/api/case")
def case_status():
    case_id = request.args.get("id")
    case = next((r for r in reports if r["id"] == case_id), None)
    if not case:
        return jsonify({"success": False, "message": "Case not found"})
    return jsonify(
        {
            "success": True,
            "data": {
                "case_id": case["id"],
                "location": case.get("location"),
                "animal_type": case.get("animal_type"),
                "injury_type": case.get("injury_type"),
                "description": case.get("description"),
                "status": case.get("status"),
                "volunteer_name": case.get("volunteer_name"),
                "treatment_stage": case.get("treatment_stage"),
                "timeline": case.get("timeline", []),
            },
        }
    )


@app.route("/api/adopt", methods=["POST"])
def adopt():
    data = request.get_json(silent=True) or {}
    adoptions.append(data)
    return jsonify({"success": True, "message": "Adoption request submitted!"})


@app.route("/donate", methods=["POST"])
@app.route("/api/donate", methods=["POST"])
def donate():
    return jsonify(
        {
            "success": False,
            "message": "Use /create-order with Razorpay checkout for donations.",
        }
    ), 400


@app.route("/create-order", methods=["POST"])
@app.route("/api/create-order", methods=["POST"])
def create_order():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Please sign in to make a donation."}), 401

    if not is_razorpay_configured():
        return jsonify(
            {
                "success": False,
                "message": "Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET before accepting payments.",
            }
        ), 503

    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return jsonify({"success": False, "message": "Please enter a valid donation amount."}), 400

    amount_paise = int(round(amount * 100))
    campaign_name = data.get("campaign_name", "").strip() or "General Rescue Fund"
    description = data.get("description", "").strip()
    frequency = data.get("frequency", "One-time").strip() or "One-time"
    receipt = f"don_{current_user['id']}_{uuid4().hex[:10]}"

    try:
        order = create_razorpay_order(
            amount_paise=amount_paise,
            receipt=receipt,
            notes={
                "user_id": str(current_user["id"]),
                "campaign_name": campaign_name,
                "frequency": frequency,
            },
        )
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return jsonify({"success": False, "message": f"Unable to create Razorpay order. {details}"}), 502
    except Exception as exc:
        return jsonify({"success": False, "message": f"Unable to create Razorpay order. {exc}"}), 502

    return jsonify(
        {
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "razorpay_key": RAZORPAY_KEY_ID,
            "donor_name": current_user["name"],
            "donor_email": current_user["email"],
            "campaign_name": campaign_name,
            "description": description,
            "frequency": frequency,
        }
    )


@app.route("/verify-payment", methods=["POST"])
@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Please sign in to verify a donation."}), 401

    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    order_id = (data.get("razorpay_order_id") or "").strip()
    payment_id = (data.get("razorpay_payment_id") or "").strip()
    signature = (data.get("razorpay_signature") or "").strip()

    if amount <= 0 or not order_id or not payment_id or not signature:
        return jsonify({"success": False, "message": "Missing payment verification details."}), 400

    if not verify_razorpay_signature(order_id, payment_id, signature):
        return jsonify({"success": False, "message": "Payment verification failed."}), 400

    campaign_name = data.get("campaign_name", "").strip() or "General Rescue Fund"
    description = data.get("description", "").strip()
    frequency = data.get("frequency", "One-time").strip() or "One-time"
    donated_at = datetime.utcnow().replace(microsecond=0).isoformat()

    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM donations WHERE payment_id = ? OR transaction_id = ?",
            (payment_id, payment_id),
        ).fetchone()
        if existing:
            totals = donation_totals()
            return jsonify(
                {
                    "success": True,
                    "message": "Donation Successful!",
                    "payment_id": payment_id,
                    "total": totals["total_amount"],
                }
            )

        conn.execute(
            """
            INSERT INTO donations (
                user_id,
                amount,
                donated_at,
                description,
                campaign_name,
                frequency,
                status,
                transaction_id,
                payment_id,
                razorpay_order_id
            ) VALUES (?, ?, ?, ?, ?, ?, 'success', ?, ?, ?)
            """,
            (
                current_user["id"],
                amount,
                donated_at,
                description,
                campaign_name,
                frequency,
                payment_id,
                payment_id,
                order_id,
            ),
        )
        conn.commit()

    totals = donation_totals()
    return jsonify(
        {
            "success": True,
            "message": "Donation Successful!",
            "payment_id": payment_id,
            "total": totals["total_amount"],
        }
    )


@app.route("/api/volunteer", methods=["POST"])
def volunteer():
    data = request.get_json(silent=True) or {}
    volunteers.append(data)
    return jsonify({"success": True, "message": "Volunteer application submitted!"})


@app.route("/api/lost_found", methods=["GET", "POST"])
def lost_found_route():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        lost_found.append(data)
        return jsonify({"success": True, "message": "Post submitted!"})

    posts = lost_found
    loc = request.args.get("location")
    if loc:
        posts = [p for p in posts if loc.lower() in p.get("location", "").lower()]
    animal_type = request.args.get("type")
    if animal_type:
        posts = [p for p in posts if p.get("animal_type") == animal_type]
    post_type = request.args.get("post_type")
    if post_type:
        posts = [p for p in posts if p.get("post_type") == post_type]
    return jsonify({"data": posts})


@app.route("/api/admin", methods=["POST"])
def admin():
    data = request.get_json(silent=True) or {}
    pwd = data.get("password")
    action = data.get("action")
    if pwd != ADMIN_PASSWORD:
        return jsonify({"success": False, "message": "Invalid password"})

    if action == "get_stats":
        return jsonify({"success": True, "data": site_stats()})
    if action == "get_reports":
        return jsonify({"success": True, "data": reports})
    if action == "get_adoption_requests":
        return jsonify({"success": True, "data": adoptions})
    if action == "get_donations":
        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT d.id, u.name, d.amount, d.frequency, d.description, d.donated_at
                FROM donations d
                JOIN users u ON u.id = d.user_id
                ORDER BY d.donated_at DESC
                """
            ).fetchall()
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "amount": float(row["amount"]),
                        "frequency": row["frequency"],
                        "message": row["description"],
                        "donated_at": row["donated_at"],
                    }
                    for row in rows
                ],
                "total": donation_totals()["total_amount"],
            }
        )
    if action == "get_volunteers":
        return jsonify({"success": True, "data": volunteers})
    if action == "update_case_status":
        case_id = data.get("case_id")
        status = data.get("status")
        note = data.get("note")
        case = next((r for r in reports if r["id"] == case_id), None)
        if case:
            case["status"] = status
            case["timeline"].append({"status": status, "time": "Now", "note": note})
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Case not found"})
    if action == "approve_adoption":
        return jsonify({"success": True})
    if action == "get_medical":
        return jsonify({"success": True, "data": []})
    if action == "update_medical":
        return jsonify({"success": True, "message": "Medical record added."})
    return jsonify({"success": False, "message": "Unknown action"})

init_db()


def handler(environ, start_response):
    return app(environ, start_response)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
