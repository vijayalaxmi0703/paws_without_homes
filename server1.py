from flask import Flask, request, jsonify, send_from_directory
import random
import os
import json
app = Flask(__name__)

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, 'images')

# Mock data storage
animals = []
animals_file = os.path.join(BASE_DIR, "animals.json")

if os.path.exists(animals_file):
    with open(animals_file, "r", encoding="utf-8") as f:
        animals = json.load(f)
donations = []
adoptions = []
volunteers = []
reports = []
lost_found = []
@app.route('/api/animals')
def get_animals():
    with open('animals.json', 'r', encoding='utf-8') as f:
        animals = json.load(f)

    return jsonify({
        "success": True,
        "data": animals
    })
@app.route('/')
def index():
    return open('index.html', encoding='utf-8').read()

@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/api/report', methods=['POST'])
def report():
    data = request.json
    case_id = f"PAW{random.randint(1000, 9999)}"
    reports.append({"id": case_id, **data, "status": "Reported", "timeline": [{"status": "Reported", "time": "Now"}]})
    return jsonify({"success": True, "message": f"Report submitted! Case ID: {case_id}"})

@app.route('/api/case')
def case_status():
    case_id = request.args.get('id')
    case = next((r for r in reports if r["id"] == case_id), None)
    if not case:
        return jsonify({"success": False, "message": "Case not found"})
    return jsonify({
        "success": True,
        "data": {
            "id": case_id,
            "status": case["status"],
            "timeline": case["timeline"]
        }
    })


@app.route('/api/adopt', methods=['POST'])
def adopt():
    data = request.json
    adoptions.append(data)
    return jsonify({"success": True, "message": "Adoption request submitted!"})

@app.route('/api/donate', methods=['POST'])
def donate():
    data = request.json or {}
    try:
        amt = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amt = 0.0
    record = {**data, "amount": amt}
    donations.append(record)
    total = sum(d["amount"] for d in donations)         
    return jsonify({"success": True,
                    "message": "Donation submitted!",
                    "total": total})

@app.route('/api/volunteer', methods=['POST'])
def volunteer():
    data = request.json
    volunteers.append(data)
    return jsonify({"success": True, "message": "Volunteer application submitted!"})

@app.route('/api/lost_found', methods=['GET', 'POST'])
def lost_found_route():
    if request.method == 'POST':
        data = request.json
        lost_found.append(data)
        return jsonify({"success": True, "message": "Post submitted!"})
    else:
        posts = lost_found
        loc = request.args.get('location')
        if loc:
            posts = [p for p in posts if loc.lower() in p.get('location', '').lower()]
        animal_type = request.args.get('type')
        if animal_type:
            posts = [p for p in posts if p.get('animal_type') == animal_type]
        post_type = request.args.get('post_type')
        if post_type:
            posts = [p for p in posts if p.get('post_type') == post_type]
        return jsonify({"data": posts})

@app.route('/api/admin', methods=['POST'])
def admin():
    data = request.json
    pwd = data.get('password')
    action = data.get('action')
    if pwd != 'admin123':
        return jsonify({"success": False, "message": "Invalid password"})
    
    if action == 'get_stats':
        total_donations = sum(d["amount"] for d in donations if isinstance(d["amount"], (int, float)))
        return jsonify({"success": True, "data": {
            "rescued": len(reports),
            "adopted": len(adoptions),
            "volunteers": len(volunteers),
            "total_donations": total_donations
        }})
    elif action == 'get_reports':
        return jsonify({"success": True, "data": reports})
    elif action == 'get_adoption_requests':
        return jsonify({"success": True, "data": adoptions})
    elif action == 'get_donations':
        total = sum(d["amount"] for d in donations if isinstance(d["amount"], (int, float)))
        return jsonify({"success": True, "data": donations, "total": total})
    elif action == 'get_volunteers':
        return jsonify({"success": True, "data": volunteers})
    elif action == 'update_case_status':
        case_id = data.get('case_id')
        status = data.get('status')
        note = data.get('note')
        case = next((r for r in reports if r["id"] == case_id), None)
        if case:
            case["status"] = status
            case["timeline"].append({"status": status, "time": "Now", "note": note})
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Case not found"})
    elif action == 'approve_adoption':
        req_id = data.get('req_id')
        decision = data.get('decision')
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Unknown action"})

# ← MOVED: This must be at the END of the file
if __name__ == "__main__":
    app.run(debug=True)