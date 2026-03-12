#!/usr/bin/env python3
"""
Paws Without Homes - Backend Server
Pure Python HTTP server with file-based JSON storage
No SQL, No Django/Flask, No external databases
"""

import json
import os
import re
import random
import string
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── DATA DIRECTORY ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "animals":           os.path.join(DATA_DIR, "animals.json"),
    "report_cases":      os.path.join(DATA_DIR, "report_cases.json"),
    "adoption_requests": os.path.join(DATA_DIR, "adoption_requests.json"),
    "volunteers":        os.path.join(DATA_DIR, "volunteers.json"),
    "donations":         os.path.join(DATA_DIR, "donations.json"),
    "medical_records":   os.path.join(DATA_DIR, "medical_records.json"),
    "lost_found":        os.path.join(DATA_DIR, "lost_found.json"),
}

ADMIN_PASSWORD = "admin123"

# ─── FILE HELPERS ───────────────────────────────────────────────────────────────
def read_json(key):
    try:
        with open(FILES[key], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def write_json(key, data):
    with open(FILES[key], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_case_id():
    cases = read_json("report_cases")
    if not cases:
        return "PAW1001"
    numbers = [int(c["case_id"].replace("PAW", "")) for c in cases if c.get("case_id", "").startswith("PAW")]
    return f"PAW{max(numbers) + 1 if numbers else 1001}"

def generate_id(prefix, key):
    items = read_json(key)
    if not items:
        return f"{prefix}001"
    ids = [int(i.get("id", "0").replace(prefix, "") or 0) for i in items if i.get("id", "").startswith(prefix)]
    return f"{prefix}{str(max(ids) + 1 if ids else 1).zfill(3)}"

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ─── API HANDLERS ───────────────────────────────────────────────────────────────
def api_get_animals(params):
    animals = read_json("animals")
    animal_type = params.get("type", [""])[0].strip()
    if animal_type:
        animals = [a for a in animals if a.get("type", "").lower() == animal_type.lower()]
    return {"success": True, "data": animals}

def api_report_animal(body):
    required = ["location", "animal_type", "injury_type", "description", "contact"]
    for r in required:
        if not body.get(r):
            return {"success": False, "message": f"Field '{r}' is required."}
    
    case_id = generate_case_id()
    case = {
        "case_id": case_id,
        "location": body["location"],
        "animal_type": body["animal_type"],
        "injury_type": body["injury_type"],
        "description": body["description"],
        "contact": body["contact"],
        "status": "Reported",
        "reported_at": now(),
        "timeline": [{"status": "Reported", "time": now(), "note": "Case filed by community member"}]
    }
    cases = read_json("report_cases")
    cases.append(case)
    write_json("report_cases", cases)
    return {"success": True, "case_id": case_id, "message": f"Case {case_id} filed successfully!"}

def api_check_case(params):
    case_id = params.get("id", [""])[0].strip().upper()
    if not case_id:
        return {"success": False, "message": "Case ID required."}
    cases = read_json("report_cases")
    case = next((c for c in cases if c["case_id"] == case_id), None)
    if not case:
        return {"success": False, "message": f"No case found with ID {case_id}"}
    return {"success": True, "data": case}

def api_adopt(body):
    required = ["animal_id", "name", "email", "phone", "address", "reason"]
    for r in required:
        if not body.get(r):
            return {"success": False, "message": f"Field '{r}' is required."}
    
    animals = read_json("animals")
    animal = next((a for a in animals if a["id"] == body["animal_id"]), None)
    if not animal:
        return {"success": False, "message": "Animal not found."}
    if animal.get("status") != "Available":
        return {"success": False, "message": "This animal is not available for adoption."}
    
    req_id = generate_id("REQ", "adoption_requests")
    request = {
        "id": req_id,
        "animal_id": body["animal_id"],
        "animal_name": animal["name"],
        "animal_type": animal["type"],
        "applicant_name": body["name"],
        "email": body["email"],
        "phone": body["phone"],
        "address": body["address"],
        "reason": body["reason"],
        "status": "Pending",
        "applied_at": now()
    }
    requests = read_json("adoption_requests")
    requests.append(request)
    write_json("adoption_requests", requests)
    return {"success": True, "id": req_id, "message": f"Adoption request {req_id} submitted! We'll contact you within 48 hours."}

def api_volunteer(body):
    required = ["name", "area", "contact", "availability"]
    for r in required:
        if not body.get(r):
            return {"success": False, "message": f"Field '{r}' is required."}
    
    v_id = generate_id("VOL", "volunteers")
    volunteer = {
        "id": v_id,
        "name": body["name"],
        "area": body["area"],
        "contact": body["contact"],
        "availability": body["availability"],
        "skills": body.get("skills", ""),
        "assigned_cases": [],
        "joined_at": now(),
        "points": 0,
        "badges": [],
        "level": 1
    }
    volunteers = read_json("volunteers")
    volunteers.append(volunteer)
    write_json("volunteers", volunteers)
    return {"success": True, "id": v_id, "message": f"Welcome aboard, {body['name']}! Volunteer ID: {v_id}"}

def api_donate(body):
    required = ["name", "amount", "frequency"]
    for r in required:
        if not body.get(r):
            return {"success": False, "message": f"Field '{r}' is required."}
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return {"success": False, "message": "Invalid donation amount."}
    
    d_id = generate_id("DON", "donations")
    donation = {
        "id": d_id,
        "name": body["name"],
        "email": body.get("email", ""),
        "amount": amount,
        "frequency": body["frequency"],
        "message": body.get("message", ""),
        "donated_at": now()
    }
    donations = read_json("donations")
    donations.append(donation)
    write_json("donations", donations)
    
    total = sum(d["amount"] for d in donations)
    return {
        "success": True,
        "id": d_id,
        "message": f"Thank you {body['name']}! ₹{amount:.0f} donated. Total raised: ₹{total:.0f}",
        "total": total
    }

def api_lost_found(body):
    required = ["post_type", "animal_type", "location", "description", "contact"]
    for r in required:
        if not body.get(r):
            return {"success": False, "message": f"Field '{r}' is required."}
    
    lf_id = generate_id("LF", "lost_found")
    post = {
        "id": lf_id,
        "post_type": body["post_type"],
        "animal_type": body["animal_type"],
        "name": body.get("name", "Unknown"),
        "location": body["location"],
        "description": body["description"],
        "contact": body["contact"],
        "date": body.get("date", now()[:10]),
        "posted_at": now(),
        "status": "Active"
    }
    posts = read_json("lost_found")
    posts.append(post)
    write_json("lost_found", posts)
    return {"success": True, "id": lf_id, "message": f"Post {lf_id} published!"}

def api_search_lost_found(params):
    posts = read_json("lost_found")
    location = params.get("location", [""])[0].strip().lower()
    animal_type = params.get("type", [""])[0].strip().lower()
    post_type = params.get("post_type", [""])[0].strip().lower()
    
    if location:
        posts = [p for p in posts if location in p.get("location", "").lower()]
    if animal_type:
        posts = [p for p in posts if p.get("animal_type", "").lower() == animal_type]
    if post_type:
        posts = [p for p in posts if p.get("post_type", "").lower() == post_type]
    
    return {"success": True, "data": posts}

# ─── ADMIN HANDLERS ─────────────────────────────────────────────────────────────
def api_admin(body):
    if body.get("password") != ADMIN_PASSWORD:
        return {"success": False, "message": "Invalid password."}
    
    action = body.get("action")
    
    if action == "get_reports":
        return {"success": True, "data": read_json("report_cases")}
    
    elif action == "get_donations":
        donations = read_json("donations")
        total = sum(d["amount"] for d in donations)
        return {"success": True, "data": donations, "total": total}
    
    elif action == "get_adoption_requests":
        return {"success": True, "data": read_json("adoption_requests")}
    
    elif action == "get_volunteers":
        return {"success": True, "data": read_json("volunteers")}
    
    elif action == "get_medical":
        return {"success": True, "data": read_json("medical_records")}
    
    elif action == "update_case_status":
        case_id = body.get("case_id")
        new_status = body.get("status")
        note = body.get("note", "")
        valid_statuses = ["Reported", "Rescued", "Under Treatment", "Adopted"]
        if new_status not in valid_statuses:
            return {"success": False, "message": "Invalid status."}
        cases = read_json("report_cases")
        for case in cases:
            if case["case_id"] == case_id:
                case["status"] = new_status
                case.setdefault("timeline", []).append({
                    "status": new_status, "time": now(), "note": note
                })
                write_json("report_cases", cases)
                return {"success": True, "message": f"Case {case_id} updated to '{new_status}'."}
        return {"success": False, "message": "Case not found."}
    
    elif action == "approve_adoption":
        req_id = body.get("req_id")
        decision = body.get("decision", "Approved")
        requests = read_json("adoption_requests")
        for req in requests:
            if req["id"] == req_id:
                req["status"] = decision
                req["decided_at"] = now()
                if decision == "Approved":
                    animals = read_json("animals")
                    for a in animals:
                        if a["id"] == req["animal_id"]:
                            a["status"] = "Adopted"
                            break
                    write_json("animals", animals)
                write_json("adoption_requests", requests)
                return {"success": True, "message": f"Request {req_id} {decision}."}
        return {"success": False, "message": "Request not found."}
    
    elif action == "update_medical":
        animal_id = body.get("animal_id")
        records = read_json("medical_records")
        rec_id = generate_id("MED", "medical_records")
        record = {
            "id": rec_id,
            "animal_id": animal_id,
            "treatment": body.get("treatment", ""),
            "vaccination_date": body.get("vaccination_date", ""),
            "sterilized": body.get("sterilized", False),
            "recovery_notes": body.get("recovery_notes", ""),
            "updated_at": now(),
            "updated_by": "Admin"
        }
        records.append(record)
        write_json("medical_records", records)
        return {"success": True, "message": "Medical record added."}
    
    elif action == "assign_volunteer":
        vol_id = body.get("vol_id")
        case_id = body.get("case_id")
        volunteers = read_json("volunteers")
        for v in volunteers:
            if v["id"] == vol_id:
                v.setdefault("assigned_cases", []).append({"case_id": case_id, "assigned_at": now()})
                write_json("volunteers", volunteers)
                return {"success": True, "message": f"Volunteer {vol_id} assigned to case {case_id}."}
        return {"success": False, "message": "Volunteer not found."}
    
    elif action == "get_stats":
        cases = read_json("report_cases")
        donations = read_json("donations")
        animals = read_json("animals")
        return {
            "success": True,
            "data": {
                "total_cases": len(cases),
                "rescued": len([c for c in cases if c["status"] in ["Rescued", "Under Treatment", "Adopted"]]),
                "adopted": len([a for a in animals if a.get("status") == "Adopted"]),
                "total_donations": sum(d["amount"] for d in donations),
                "volunteers": len(read_json("volunteers")),
                "available_animals": len([a for a in animals if a.get("status") == "Available"])
            }
        }
    
    return {"success": False, "message": "Unknown action."}

# ─── HTTP SERVER ────────────────────────────────────────────────────────────────
class PawsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_file(os.path.join(BASE_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/api/animals":
            self.send_json(api_get_animals(params))
        elif path == "/api/case":
            self.send_json(api_check_case(params))
        elif path == "/api/lost_found":
            self.send_json(api_search_lost_found(params))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except Exception:
            self.send_json({"success": False, "message": "Invalid JSON"}, 400)
            return

        path = urlparse(self.path).path
        routes = {
            "/api/report":     api_report_animal,
            "/api/adopt":      api_adopt,
            "/api/volunteer":  api_volunteer,
            "/api/donate":     api_donate,
            "/api/lost_found": api_lost_found,
            "/api/admin":      api_admin,
        }
        handler = routes.get(path)
        if handler:
            self.send_json(handler(body))
        else:
            self.send_json({"success": False, "message": "Not found"}, 404)

def run():
    port = 8080
    server = HTTPServer(("0.0.0.0", port), PawsHandler)
    print(f"🐾 Paws Without Homes server running at http://localhost:{port}")
    print("   Press Ctrl+C to stop.")
    server.serve_forever()

if __name__ == "__main__":
    run()
