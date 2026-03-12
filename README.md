# 🐾 Paws Without Homes

> **"Every Paw Deserves a Home"**

A full-stack web application to help rescue, treat, and rehome stray animals — built entirely with Python, HTML/CSS/JS, and JSON file storage. No SQL. No Django. No external databases.

---

## 🚀 How to Run

```bash
# Option 1: Use the launcher (opens browser automatically)
python start.py

# Option 2: Run server directly
python server.py
# Then open: http://localhost:8080
```

**Requirements:** Python 3.7+ (standard library only — no pip installs needed!)

---

## 🏗 Project Structure

```
paws-without-homes/
├── server.py          ← Python HTTP server (no Flask/Django)
├── index.html         ← Single-page frontend (HTML + CSS + JS)
├── start.py           ← Quick launcher
├── README.md
└── data/
    ├── animals.json           ← Adoptable animals
    ├── report_cases.json      ← Rescue reports (PAW1001, PAW1002...)
    ├── adoption_requests.json ← Adoption applications
    ├── volunteers.json        ← Volunteer registrations
    ├── donations.json         ← Donation records
    ├── medical_records.json   ← Medical history
    └── lost_found.json        ← Lost & found posts
```

---

## 📋 Features

| Module | Features |
|---|---|
| 🆘 **Report** | File rescue reports, generate Case IDs (PAW1001+), track status |
| 🏠 **Adopt** | Browse animals, filter by type, apply for adoption with form |
| 💖 **Donate** | One-time/monthly donations, impact calculator, live total |
| 🤝 **Volunteer** | Register volunteers, availability slots |
| 🔎 **Lost & Found** | Post lost/found alerts, search by location & type |
| 📚 **Awareness** | Animal laws, first aid, adoption vs buying, sterilization info |
| 🛠 **Admin Panel** | Password-protected, manage all data, update statuses |

---

## 🔐 Admin Access

- **URL:** http://localhost:8080 → click Admin
- **Password:** `admin123`

Admin can:
- View & update all rescue case statuses
- Approve/reject adoption requests
- View all donations with totals
- Manage volunteers
- Add medical records

---

## 💾 Technical Details

- **Backend:** Python `http.server` (stdlib only)
- **Storage:** JSON files via Python's `json` module
- **Frontend:** Pure HTML5 + CSS3 + Vanilla JavaScript
- **Case IDs:** Auto-generated (PAW1001, PAW1002, ...)
- **No SQL, No ORM, No external packages**

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/animals?type=Dog` | List animals |
| GET | `/api/case?id=PAW1001` | Check case status |
| GET | `/api/lost_found?location=Mumbai` | Search lost & found |
| POST | `/api/report` | File a rescue report |
| POST | `/api/adopt` | Submit adoption request |
| POST | `/api/donate` | Make a donation |
| POST | `/api/volunteer` | Register as volunteer |
| POST | `/api/lost_found` | Post lost/found alert |
| POST | `/api/admin` | Admin operations (password-protected) |
