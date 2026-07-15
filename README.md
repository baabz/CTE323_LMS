# CTE323 — Python Programming Language Portal

A full-featured **Learning Management System (LMS)** built with **Python Flask** for the CTE323 course at Kaduna Polytechnic.

## Features

### 👩‍🏫 Admin / Lead Lecturer
- Dashboard with live statistics
- Upload & manage course handouts
- Create **Assignment Tasks** with deadlines
- Automatic **late submission detection**
- Grade and give feedback on student submissions
- Post **Announcements** (with pin-to-top)
- Post to the public Class Feed (image or YouTube link)
- Manage teaching staff accounts

### 🧑‍🔬 Lab Assistant (Sub-Teacher)
- Upload handouts
- Post to Class Feed

### 👨‍🎓 Students
- Register & log in with matric number
- Customise profile (display name + profile picture)
- Browse and download course handouts
- Submit assignments (`.py`, `.pdf`, `.zip`) linked to specific tasks
- View submission history with grade & feedback
- **Announcements** board with unread badge
- Upcoming deadline tracker on dashboard

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 · Flask |
| Database | SQLite (via `sqlite3`) |
| Frontend | Vanilla HTML / CSS / JS |
| Styling | Custom dark-theme design system |
| Icons | Bootstrap Icons (CDN) |
| Fonts | Google Fonts — Inter |

## Project Structure

```
CTE323_portal/
├── app.py                  # Flask application & all routes
├── models.py               # Database queries (SQLite)
├── schema.sql              # DB schema (tables & seed data)
├── requirements.txt        # Python dependencies
├── static/
│   └── css/, uploads/      # Styles & uploaded files
└── templates/
    ├── base.html           # Shared layout (sidebar, nav)
    ├── student/            # Student-facing pages
    ├── teacher/            # Admin/lecturer pages
    └── sub_teacher/        # Lab assistant pages
```

## Setup & Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/CTE323_portal.git
cd CTE323_portal

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Visit **http://127.0.0.1:5000**

### Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Lead Lecturer | `Musa Yahya` | `260697` |

> ⚠️ Change these before deploying to production.

## Deployment

For production hosting (e.g. PythonAnywhere, Render, Railway):
1. Set a strong `SECRET_KEY` in an environment variable
2. Replace the dev server with **Gunicorn**: `gunicorn app:app`
3. Use a persistent file storage solution for uploads

## License

Academic project — Kaduna Polytechnic, Department of Computer Engineering Technology.
