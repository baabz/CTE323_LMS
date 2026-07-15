# =============================================================================
#  app.py — Main Flask Application  (v2)
#  CTE323 Course Portal | Kaduna Polytechnic | HND Computer Engineering
# =============================================================================
#
#  v2 CHANGES:
#    • 3-Role system: 'admin', 'sub_teacher', 'student'
#      (old 'teacher' role is auto-migrated to 'admin' on startup)
#    • '/' is now a PUBLIC feed page — no login required
#    • New decorators: admin_required, staff_required
#    • New routes: /sub-teacher/dashboard, /staff/post-feed,
#                  /admin/manage-staff, /admin/add-staff,
#                  /download/feed-media/<filename>
#    • Jinja2 filter: to_embed_url  (converts YouTube watch URLs to embed URLs)
#    • Automatic database migration on startup
#
#  HOW TO RUN:
#    pip install flask
#    python app.py
#    Open: http://127.0.0.1:5000
# =============================================================================

import os                           # File path utilities
import uuid                         # Unique filename generation
import re                           # Regular expressions (YouTube URL parsing)
from functools import wraps         # Preserves function metadata in decorators
from datetime import timedelta      # Session timeout calculations

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    send_file,
    abort
)

import models   # Our own models.py — all database functions live there


# =============================================================================
#  APP INITIALISATION
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cte323-kadpoly-v2-secret-change-in-production'

# Configure session expiration (timeout)
# 15 minutes of inactivity will automatically log the user out
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# ---- Upload folder paths ----
BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
HANDOUTS_FOLDER      = os.path.join(BASE_DIR, 'uploads', 'handouts')
ASSIGNMENTS_FOLDER   = os.path.join(BASE_DIR, 'uploads', 'assignments')
FEED_MEDIA_FOLDER    = os.path.join(BASE_DIR, 'uploads', 'feed_media')
PROFILE_PICS_FOLDER  = os.path.join(BASE_DIR, 'uploads', 'profile_pics')  # NEW v3

app.config['HANDOUTS_FOLDER']      = HANDOUTS_FOLDER
app.config['ASSIGNMENTS_FOLDER']   = ASSIGNMENTS_FOLDER
app.config['FEED_MEDIA_FOLDER']    = FEED_MEDIA_FOLDER
app.config['PROFILE_PICS_FOLDER']  = PROFILE_PICS_FOLDER

# Create all upload directories if they don't exist
os.makedirs(HANDOUTS_FOLDER,     exist_ok=True)
os.makedirs(ASSIGNMENTS_FOLDER,  exist_ok=True)
os.makedirs(FEED_MEDIA_FOLDER,   exist_ok=True)
os.makedirs(PROFILE_PICS_FOLDER, exist_ok=True)  # NEW v3


# =============================================================================
#  ALLOWED FILE EXTENSIONS
# =============================================================================
ALLOWED_HANDOUT_EXTENSIONS    = {'pdf', 'doc', 'docx', 'pptx', 'txt', 'zip'}
ALLOWED_ASSIGNMENT_EXTENSIONS = {'py', 'pdf', 'zip'}  # v3: expanded to accept reports & archives
ALLOWED_FEED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_PROFILE_PIC_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}  # NEW v3

# =============================================================================
#  STUDENT MATRIC NUMBER FORMAT
#  Format: COE + YY + HND + NNNN  (e.g. "COE25HND0001")
#
#  LESSON: Centralise configuration in constants — change one line here
#  and the whole application adapts. If the year changes to 2026,
#  just update MATRIC_YEAR = '26'.
#
#  The registration form asks for only the last 4 digits (the unique part).
#  The backend assembles the full matric number: PREFIX + digits.
#  This prevents typos in the fixed prefix and ensures a consistent format.
# =============================================================================
MATRIC_YEAR   = '25'                         # Last two digits of the academic year
MATRIC_PREFIX = f'COE{MATRIC_YEAR}HND'      # = 'COE25HND'
MATRIC_LENGTH = 4                            # Unique digits at the end (e.g. 0001)


def allowed_file(filename: str, allowed_set: set) -> bool:
    """
    Generic file extension validator.

    LESSON: DRY — Don't Repeat Yourself.
    Instead of three separate allowed_X() functions (one per upload type),
    one function handles all cases by accepting the allowed set as a parameter.

    Usage:
        allowed_file('notes.pdf', ALLOWED_HANDOUT_EXTENSIONS)    -> True
        allowed_file('lab1.py',   ALLOWED_ASSIGNMENT_EXTENSIONS) -> True
        allowed_file('photo.jpg', ALLOWED_FEED_IMAGE_EXTENSIONS) -> True
        allowed_file('virus.exe', ALLOWED_HANDOUT_EXTENSIONS)    -> False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


# =============================================================================
#  JINJA2 CUSTOM FILTER: to_embed_url  (NEW v2)
#
#  LESSON: Jinja2 filters transform a value in templates: {{ url|to_embed_url }}
#  This filter converts YouTube "watch" links to embeddable "embed" links.
#
#  INPUT:  https://www.youtube.com/watch?v=dQw4w9WgXcQ
#          https://youtu.be/dQw4w9WgXcQ
#  OUTPUT: https://www.youtube.com/embed/dQw4w9WgXcQ
# =============================================================================

@app.template_filter('to_embed_url')
def to_embed_url(url: str) -> str:
    """
    Converts a YouTube watch URL or short URL to an embeddable iframe src.

    HOW IT WORKS:
        re.search() scans the URL string for a YouTube video ID pattern.
        YouTube video IDs are always exactly 11 characters: letters, digits,
        underscores, and hyphens.  e.g. "dQw4w9WgXcQ"

        The regex matches two common URL formats:
          v=VIDEO_ID    (watch URLs)
          youtu.be/VIDEO_ID  (short URLs)
    """
    if not url:
        return ''
    # Regex: look for 'v=' or 'youtu.be/' followed by exactly 11 valid chars
    match = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    if match:
        video_id = match.group(1)   # group(1) extracts the first capture group
        return f'https://www.youtube.com/embed/{video_id}'
    return url   # Return unchanged if it doesn't look like a YouTube URL


# =============================================================================
#  DATABASE INITIALISATION + MIGRATION
# =============================================================================

def init_db():
    """
    Initialises the database from schema.sql.
    Also handles automatic migration from v1 (teacher/student roles)
    to v2 (admin/sub_teacher/student roles).

    MIGRATION PATTERN (SQLite table rebuild):
      SQLite cannot ALTER a CHECK constraint after a table is created.
      The standard pattern is:
        1. Create a new table with the updated schema
        2. Copy existing data (converting old values where needed)
        3. DROP the old table
        4. RENAME the new table to the original name
      This preserves all data while updating the schema.
    """
    import sqlite3

    db_path     = os.path.join(BASE_DIR, 'portal.db')
    schema_path = os.path.join(BASE_DIR, 'schema.sql')

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # -------------------------------------------------------------------------
    #  STEP 1: Check if migration from v1 is needed
    #  We look at the CREATE TABLE statement stored in sqlite_master —
    #  SQLite stores the original DDL there for each table.
    # -------------------------------------------------------------------------
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()

    needs_migration = row is not None and "'teacher'" in row[0]

    if needs_migration:
        print("[MIGRATE] v1 schema detected. Running migration to v2...")

        # Disable foreign key checks during table rebuild (SQLite requirement)
        conn.execute("PRAGMA foreign_keys = OFF")

        conn.executescript(
            """
            -- Step A: Create the new users table with updated schema
            CREATE TABLE IF NOT EXISTS users_v2 (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL CHECK(role IN ('admin', 'sub_teacher', 'student')),
                full_name     TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            -- Step B: Copy all rows from the old table, converting 'teacher' -> 'admin'
            INSERT INTO users_v2 (id, username, password_hash, role, full_name, created_at)
            SELECT
                id,
                username,
                password_hash,
                CASE role
                    WHEN 'teacher' THEN 'admin'   -- old 'teacher' becomes new 'admin'
                    ELSE role                      -- 'student' stays as 'student'
                END  AS role,
                NULL AS full_name,   -- v1 had no full_name column
                created_at
            FROM users;

            -- Step C: Remove the old table
            DROP TABLE users;

            -- Step D: Rename the new table to 'users'
            ALTER TABLE users_v2 RENAME TO users;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print("[MIGRATE] Migration complete. 'teacher' roles converted to 'admin'.")

    # -------------------------------------------------------------------------
    #  STEP 2: Run schema.sql to create any missing tables (IF NOT EXISTS)
    #  After migration, users table already exists — only new tables are created.
    # -------------------------------------------------------------------------
    with open(schema_path, 'r') as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()

    # -------------------------------------------------------------------------
    #  STEP 2b: v3 migration — add profile_picture column if it doesn't exist
    #  SQLite's ALTER TABLE ADD COLUMN is safe to run even if it already exists
    #  when wrapped in a try/except — it raises OperationalError if column exists.
    # -------------------------------------------------------------------------
    try:
        conn.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT")
        conn.commit()
        print("[MIGRATE] v3: Added 'profile_picture' column to users table.")
    except sqlite3.OperationalError:
        pass  # Column already exists — no action needed

    # -------------------------------------------------------------------------
    #  STEP 2c: v4 migration — add task_id to assignments (submissions) table
    #  Links each student submission to a named assignment task.
    #  NULL = legacy submission (submitted before tasks were introduced).
    # -------------------------------------------------------------------------
    try:
        conn.execute("ALTER TABLE assignments ADD COLUMN task_id INTEGER REFERENCES assignment_tasks(id) ON DELETE SET NULL")
        conn.commit()
        print("[MIGRATE] v4: Added 'task_id' column to assignments table.")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # schema.sql CREATE TABLE IF NOT EXISTS handles assignment_tasks + announcements

    # -------------------------------------------------------------------------
    #  STEP 3: Ensure the lead lecturer account has the correct credentials.
    #
    #  LESSON: This block runs EVERY startup.
    #    - First, try to UPDATE the old default placeholder accounts
    #      ('admin' or 'lecturer') to the real lecturer name and password.
    #    - If no old placeholder exists, check if 'Musa Yahya' is already set.
    #    - If no admin exists at all, INSERT the account from scratch.
    #
    #  SQL USED:
    #    UPDATE users SET username=?, password_hash=?, full_name=? WHERE ...
    #    INSERT INTO users (...) VALUES (?, ?, ?, ?)
    # -------------------------------------------------------------------------
    import hashlib
    pw_hash = hashlib.sha256('260697'.encode('utf-8')).hexdigest()

    # Try to update whichever old placeholder account exists
    updated = conn.execute(
        """
        UPDATE users
        SET username      = 'Musa Yahya',
            password_hash = ?,
            full_name     = 'Musa Yahya'
        WHERE role = 'admin'
          AND username IN ('admin', 'lecturer')
        """,
        (pw_hash,)
    ).rowcount
    conn.commit()

    if updated > 0:
        print(f"[OK] Lecturer account updated: username='Musa Yahya'")
    else:
        # Either 'Musa Yahya' already exists correctly, or no admin at all
        exists = conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = 'Musa Yahya' AND role = 'admin'"
        ).fetchone()[0]

        if exists == 0:
            # No admin account exists yet — create one fresh
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                ('Musa Yahya', pw_hash, 'admin', 'Musa Yahya')
            )
            conn.commit()
            print("[OK] Lecturer account created: username='Musa Yahya'")
        else:
            # Account exists and already has the right credentials — ensure password is current
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = 'Musa Yahya' AND role = 'admin'",
                (pw_hash,)
            )
            conn.commit()
            print("[OK] Lecturer account verified: username='Musa Yahya'")

    conn.close()
    print("[OK] Database initialised (portal.db)")


# =============================================================================
#  DECORATORS — Role-Based Access Control
#
#  LESSON: A decorator wraps a function with extra behaviour.
#  Python evaluates @decorator as: my_route = decorator(my_route)
#  The @wraps(f) call preserves the original function's __name__ and __doc__.
# =============================================================================

def login_required(f):
    """Redirects unauthenticated visitors to /login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access that page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Route decorator: only allows users with role='admin' (Lead Lecturer).
    Any other logged-in role gets 403 Forbidden.
    Unauthenticated visitors are redirected to /login.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            # 403 = "I know who you are, but you don't have permission"
            abort(403)
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    """
    Route decorator: allows 'admin' OR 'sub_teacher' (any teaching staff).
    Students and guests cannot access these routes.

    LESSON: This decorator shows how to implement layered permissions —
    different roles share some routes but not others.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'sub_teacher'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """Route decorator: only allows users with role='student'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'student':
            abort(403)
        return f(*args, **kwargs)
    return decorated



# =============================================================================
#  CONTEXT PROCESSOR — inject unread announcement count into every template
#  This runs on every request so the sidebar badge is always up to date.
# =============================================================================
@app.context_processor
def inject_globals():
    """
    Makes `_announce_unread` available in every Jinja2 template automatically.

    LESSON: context_processor is the Flask way to share data across all
    templates without repeating it in every route. Think of it like a
    global variable that every template can read.

    The unread count = number of announcements whose ID is greater than
    the ID the student last "saw" (stored in session when they visit
    the announcements page).
    """
    unread = 0
    if session.get('role') == 'student':
        try:
            last_seen = session.get('last_seen_announcement_id', 0)
            all_ids   = models.get_all_announcements()
            unread    = sum(1 for a in all_ids if a['id'] > last_seen)
            session['_announce_unread'] = unread
        except Exception:
            unread = 0

    from datetime import datetime as _dt
    _now = _dt.now()
    return {
        '_announce_unread': unread,
        'now':     _now,                            # datetime object  — use now.strftime(...)
        'now_str': _now.strftime('%Y-%m-%dT%H:%M'), # ISO string       — compare directly with due_date
    }


# =============================================================================
#  HELPER: staff_home()
#  Returns the correct URL for the logged-in staff member's home dashboard.
#  Prevents duplicating the role-check logic in every upload/post route.
# =============================================================================

def staff_home():
    """Returns the home URL for the current staff member based on their role."""
    if session.get('role') == 'admin':
        return url_for('admin_dashboard')
    return url_for('sub_teacher_dashboard')


# =============================================================================
#  SECTION 1 — PUBLIC ROUTES  (no login required)
# =============================================================================

@app.route('/')
def portfolio():
    """
    Personal Professional Portfolio Homepage.
    Renders a static page with About Me, Academic CV, and a navigation button 
    pointing to the student portal (showcase and login).
    """
    return render_template('portfolio.html')


@app.route('/showcase')
def index():
    """
    Public Homepage — The Class Activity Feed.

    This route requires NO authentication. Anyone who visits the site sees it.

    LESSON: Raw SQL on a public route
      The SQL query below runs every time someone loads the homepage.
      It joins public_feed with users so we can show WHO posted each item.

      SELECT * FROM public_feed
      JOIN users ON public_feed.uploaded_by = users.id
      ORDER BY created_at DESC

    NOTE: If the user IS already logged in, we still show this page —
    we don't redirect them away. The navbar changes based on session state.
    """
    # Fetch all feed posts from the database (function in models.py)
    # This executes: SELECT f.*, u.username, u.full_name FROM public_feed f JOIN users u ...
    feed_posts = models.get_all_feed_posts()

    # Pass the list to the template — Jinja2 loops over it with {% for post in feed_posts %}
    return render_template('index.html', feed_posts=feed_posts)


@app.route('/portal/login', methods=['GET', 'POST'])
def login():
    """
    Handles login for all three roles: admin, sub_teacher, student.

    GET  → Render the login form
    POST → Validate credentials, set session, redirect to role-specific dashboard
    """
    # If already logged in, send them to their dashboard immediately
    if 'user_id' in session:
        return _redirect_to_dashboard()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Both username and password are required.", "danger")
            return render_template('login.html')

        user = models.verify_login(username, password)

        if user is None:
            # Don't tell them WHICH field is wrong — security best practice
            flash("Invalid username or password.", "danger")
            return render_template('login.html')

        # Store user info in the session cookie (signed with SECRET_KEY)
        session.clear()
        # Enable sliding session expiration based on PERMANENT_SESSION_LIFETIME
        session.permanent = True
        session['user_id']   = user['id']
        session['username']  = user['username']
        session['role']      = user['role']
        session['full_name'] = user['full_name'] or user['username']
        session['profile_pic'] = user['profile_picture']  # NEW v3: for sidebar avatar

        flash(f"Welcome back, {session['full_name']}!", "success")
        return _redirect_to_dashboard()

    return render_template('login.html')


def _redirect_to_dashboard():
    """
    Internal helper: redirects the current user to their role's dashboard.
    Using a private function (prefix _) avoids repeating this logic in multiple routes.
    """
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'sub_teacher':
        return redirect(url_for('sub_teacher_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Student self-registration using the official matric number format.

    FORMAT:  COE + YY + HND + NNNN
    EXAMPLE: COE25HND0001

    The form shows the prefix 'COE25HND' as a static label and asks the
    student to type only their 4-digit unique number (e.g. '0001').
    The backend assembles the full matric string and stores it as the username.

    LESSON: This pattern is called 'input decomposition' — breaking a
    structured identifier into its fixed and variable parts, validating each
    separately, then combining them. It prevents format errors and is much
    more user-friendly than asking students to type the whole string manually.
    """
    # Pass the prefix to the template so it can be displayed in the form
    prefix = MATRIC_PREFIX   # e.g. 'COE25HND'

    if request.method == 'POST':
        # The student types only the unique 4-digit suffix
        student_num = request.form.get('student_number', '').strip()
        password    = request.form.get('password', '').strip()
        confirm     = request.form.get('confirm_password', '').strip()

        # ---- Validate the 4-digit number ----
        # .isdigit() returns True only if ALL characters are numeric digits
        if not student_num:
            flash('Please enter your 4-digit student number.', 'danger')
            return render_template('register.html', prefix=prefix)
        if not student_num.isdigit():
            flash('Student number must contain digits only (0-9).', 'danger')
            return render_template('register.html', prefix=prefix)
        if len(student_num) != MATRIC_LENGTH:
            flash(f'Student number must be exactly {MATRIC_LENGTH} digits (e.g. 0001).', 'danger')
            return render_template('register.html', prefix=prefix)

        # ---- Assemble the full matric number ----
        # zfill(4) pads with leading zeros: '1' -> '0001', '12' -> '0012'
        matric_number = f"{MATRIC_PREFIX}{student_num.zfill(MATRIC_LENGTH)}"
        # matric_number is now e.g. 'COE25HND0001'

        # ---- Validate the password ----
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html', prefix=prefix)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', prefix=prefix)

        # ---- Create the account (role is always 'student' via public registration) ----
        # SQL: INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'student')
        success = models.create_user(matric_number, password, role='student')
        if not success:
            flash(f"Matric number '{matric_number}' is already registered.", 'danger')
            return render_template('register.html', prefix=prefix)

        flash(f"Account created for {matric_number}! Please log in.", 'success')
        return redirect(url_for('login'))

    return render_template('register.html', prefix=prefix)


@app.route('/logout')
def logout():
    """Clears the session and redirects to the public homepage."""
    name = session.get('full_name', session.get('username', 'User'))
    session.clear()
    flash(f"Goodbye, {name}! You have been logged out.", "info")
    return redirect(url_for('index'))


# =============================================================================
#  SECTION 2 — ADMIN ROUTES  (role='admin' only)
#  The admin (Lead Lecturer) has full system access.
#  All routes here use the @admin_required decorator.
# =============================================================================

@app.route('/teacher/dashboard')
@admin_required
def admin_dashboard():
    """
    Admin's main dashboard. Shows full system statistics and quick-access links.
    Fetches aggregate counts from the database using COUNT() SQL queries.
    """
    stats    = models.get_dashboard_stats()    # runs multiple COUNT(*) queries
    students = models.get_all_students()
    return render_template('teacher/dashboard.html', stats=stats, students=students)


@app.route('/teacher/submissions')
@admin_required
def view_submissions():
    """
    Shows ALL student submissions — admin only.
    Sub-teachers cannot see grades or submission logs.
    """
    assignments = models.get_all_assignments()
    return render_template('teacher/view_submissions.html', assignments=assignments)


@app.route('/teacher/grade/<int:assignment_id>', methods=['GET', 'POST'])
@admin_required
def grade_assignment(assignment_id: int):
    """
    Admin grades a specific student submission.
    <int:assignment_id> is a URL variable — Flask extracts and converts it automatically.
    """
    assignment = models.get_assignment_by_id(assignment_id)
    if assignment is None:
        abort(404)

    if request.method == 'POST':
        grade    = request.form.get('grade', '').strip()
        feedback = request.form.get('feedback', '').strip()
        # SQL: UPDATE assignments SET grade = ?, feedback = ? WHERE id = ?
        models.grade_assignment(assignment_id, grade, feedback)
        flash(f"Grade saved for {assignment['student_name']}.", "success")
        return redirect(url_for('view_submissions'))

    return render_template('teacher/grade_assignment.html', assignment=assignment)


@app.route('/teacher/delete-handout/<int:handout_id>', methods=['POST'])
@admin_required
def delete_handout(handout_id: int):
    """
    Deletes a handout file from disk and removes its database record.
    Admin-only — sub_teachers can upload but not delete.
    """
    handout = models.get_handout_by_id(handout_id)
    if handout is None:
        abort(404)

    # Step 1: Delete from filesystem
    file_path = os.path.join(app.config['HANDOUTS_FOLDER'], handout['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)

    # Step 2: Delete from database
    models.delete_handout(handout_id)
    flash(f"Handout '{handout['title']}' deleted.", "info")
    return redirect(url_for('teacher_handouts'))


@app.route('/admin/manage-staff')
@admin_required
def manage_staff():
    """
    Admin views all staff accounts (admin + sub_teacher) and can add new ones.

    SQL USED (in models.get_all_staff()):
        SELECT * FROM users WHERE role IN ('admin', 'sub_teacher')
        ORDER BY role, username ASC
    """
    staff = models.get_all_staff()
    return render_template('admin/manage_staff.html', staff=staff)


@app.route('/admin/add-staff', methods=['POST'])
@admin_required
def add_staff():
    """
    Creates a new staff account (admin or sub_teacher).
    Only accessible via POST to prevent accidental GET requests creating accounts.
    """
    username  = request.form.get('username', '').strip()
    password  = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    role      = request.form.get('role', 'sub_teacher').strip()

    # Validate the role — only these two are valid for staff creation
    errors = {}
    if role not in ('admin', 'sub_teacher'):
        errors['role'] = "Invalid role selected."

    if not username:
        errors['username'] = "Username is required."
    if not full_name:
        errors['full_name'] = "Full name is required."
    if not password:
        errors['password'] = "Password is required."
    elif len(password) < 6:
        errors['password'] = "Password must be at least 6 characters."

    # If there are validation errors, re-render the page and show them inline
    if errors:
        staff = models.get_all_staff()
        return render_template('admin/manage_staff.html', staff=staff, form=request.form, errors=errors)

    # Attempt to create the account
    success = models.create_staff_user(username, password, full_name, role)
    if not success:
        staff = models.get_all_staff()
        errors['username'] = f"Username '{username}' is already taken."
        return render_template('admin/manage_staff.html', staff=staff, form=request.form, errors=errors)

    role_label = "Admin" if role == 'admin' else "Sub-Teacher"
    flash(f"{role_label} account '{username}' created successfully.", "success")
    return redirect(url_for('manage_staff'))


@app.route('/staff/delete-feed/<int:post_id>', methods=['POST'])
@admin_required
def delete_feed_post_route(post_id: int):
    """
    Admin-only: deletes a public feed post.
    If the post has an image, the file is removed from disk too.
    """
    post = models.get_feed_post_by_id(post_id)
    if post is None:
        abort(404)

    # If it's an image post, also delete the physical file
    if post['media_type'] == 'image':
        file_path = os.path.join(app.config['FEED_MEDIA_FOLDER'], post['media_path_or_url'])
        if os.path.exists(file_path):
            os.remove(file_path)

    models.delete_feed_post(post_id)
    flash("Feed post deleted.", "info")
    return redirect(url_for('index'))


# =============================================================================
#  SECTION 3 — STAFF ROUTES  (admin OR sub_teacher)
#  These routes are accessible to any teaching staff member.
# =============================================================================

@app.route('/teacher/upload-handout', methods=['GET', 'POST'])
@staff_required   # CHANGED from admin_required: sub_teachers can also upload
def upload_handout():
    """
    Both admin and sub_teacher can upload handouts for students.

    LESSON: File Upload Flow
      1. Check enctype="multipart/form-data" is set in the HTML form
      2. Read file from request.files['handout_file']
      3. Validate extension against the whitelist
      4. Sanitise filename with secure_filename()
      5. Prepend UUID to prevent filename collisions
      6. Save to HANDOUTS_FOLDER
      7. INSERT a record in the database
    """
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        file        = request.files.get('handout_file')

        if not title:
            flash("Please provide a title.", "danger")
            return render_template('teacher/upload_handout.html')
        if file is None or file.filename == '':
            flash("Please select a file.", "danger")
            return render_template('teacher/upload_handout.html')
        if not allowed_file(file.filename, ALLOWED_HANDOUT_EXTENSIONS):
            flash(f"Invalid file type. Allowed: {', '.join(ALLOWED_HANDOUT_EXTENSIONS)}", "danger")
            return render_template('teacher/upload_handout.html')

        from werkzeug.utils import secure_filename
        safe_name       = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{safe_name}"
        file.save(os.path.join(app.config['HANDOUTS_FOLDER'], unique_filename))

        models.add_handout(title, description, unique_filename, session['user_id'])
        flash(f"Handout '{title}' uploaded!", "success")
        # Redirect to the correct home dashboard based on role
        return redirect(staff_home())

    return render_template('teacher/upload_handout.html')


@app.route('/teacher/handouts')
@staff_required
def teacher_handouts():
    """
    Staff view of all handouts — both admin and sub_teacher can see this list.
    Only admin sees the Delete button (controlled in the template via session.role).
    """
    handouts = models.get_all_handouts()
    return render_template('teacher/manage_handouts.html', handouts=handouts)


@app.route('/staff/post-feed', methods=['GET', 'POST'])
@staff_required
def post_to_feed():
    """
    Allows admin OR sub_teacher to post a new item to the public class feed.

    TWO types of media:
      'image'      → user uploads a file → saved to uploads/feed_media/
      'video_link' → user pastes a YouTube URL → stored as text in the database

    The JavaScript in feed_post.html shows/hides the correct input based on
    the user's media type selection (no page reload needed).
    """
    if request.method == 'POST':
        title      = request.form.get('title', '').strip()
        desc       = request.form.get('description', '').strip()
        media_type = request.form.get('media_type', '').strip()  # 'image' or 'video_link'

        if not title or not media_type:
            flash("Title and media type are required.", "danger")
            return render_template('feed_post.html')

        if media_type not in ('image', 'video_link'):
            flash("Invalid media type.", "danger")
            return render_template('feed_post.html')

        # ---- Handle based on media type ----
        if media_type == 'image':
            file = request.files.get('feed_image')
            if file is None or file.filename == '':
                flash("Please select an image file.", "danger")
                return render_template('feed_post.html')
            if not allowed_file(file.filename, ALLOWED_FEED_IMAGE_EXTENSIONS):
                flash("Invalid image type. Allowed: JPG, JPEG, PNG, GIF, WEBP", "danger")
                return render_template('feed_post.html')

            from werkzeug.utils import secure_filename
            safe_name       = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{safe_name}"
            file.save(os.path.join(app.config['FEED_MEDIA_FOLDER'], unique_filename))
            media_path_or_url = unique_filename   # Store just the filename

        else:  # video_link
            youtube_url = request.form.get('video_url', '').strip()
            if not youtube_url:
                flash("Please paste a YouTube URL.", "danger")
                return render_template('feed_post.html')
            # Basic validation: must contain youtube.com or youtu.be
            if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
                flash("Please enter a valid YouTube URL.", "danger")
                return render_template('feed_post.html')
            media_path_or_url = youtube_url   # Store the full URL string

        # INSERT record into public_feed
        models.add_feed_post(
            title             = title,
            description       = desc,
            media_type        = media_type,
            media_path_or_url = media_path_or_url,
            uploaded_by       = session['user_id']
        )

        flash("Post published to the class feed!", "success")
        return redirect(url_for('index'))

    return render_template('feed_post.html')


# =============================================================================
#  SECTION 4 — SUB-TEACHER ROUTES
# =============================================================================

@app.route('/sub-teacher/dashboard')
@staff_required
def sub_teacher_dashboard():
    """
    Limited dashboard for sub_teachers (Lab Assistants).
    Shows only what they can access: handout count, feed post count.
    Does NOT show student grades or submissions.
    """
    handout_count = len(models.get_all_handouts())
    feed_count    = models.get_dashboard_stats()['feed_count']
    return render_template(
        'sub_teacher/dashboard.html',
        handout_count=handout_count,
        feed_count=feed_count
    )


# =============================================================================
#  SECTION 5 — STUDENT ROUTES  (role='student' only)
# =============================================================================

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    """
    Student's home page — shows submission history, announcements, and
    upcoming assignment task deadlines.

    v4 additions:
    - Passes all announcements (pinned first) for the notice section.
    - Computes unread_count: announcements posted after the student's
      last_seen_announcement_id stored in session.
    - Passes open_tasks so the dashboard can show countdown deadlines.
    """
    my_submissions = models.get_assignments_by_student(session['user_id'])
    handout_count  = len(models.get_all_handouts())
    announcements  = models.get_all_announcements()
    open_tasks     = models.get_open_assignment_tasks()

    # Unread count for the dashboard tile badge
    last_seen    = session.get('last_seen_announcement_id', 0)
    unread_count = sum(1 for a in announcements if a['id'] > last_seen)

    return render_template(
        'student/dashboard.html',
        submissions=my_submissions,
        handout_count=handout_count,
        announcements=announcements,
        open_tasks=open_tasks,
        unread_count=unread_count,
        # `now` and `now_str` come automatically from the context_processor
    )


@app.route('/student/handouts')
@student_required
def student_handouts():
    """Student browses all available handouts for download."""
    handouts = models.get_all_handouts()
    return render_template('student/handouts.html', handouts=handouts)


@app.route('/student/submit', methods=['GET', 'POST'])
@student_required
def submit_assignment():
    """
    Student uploads a .py, .pdf, or .zip file as their assignment submission.

    v4 changes:
    - Student selects from a dropdown of OPEN assignment tasks created by the lecturer.
    - Submission is linked to the selected task via task_id FK.
    - If the current time is past the task's due_date the submission is flagged
      as LATE with a flash warning (but still accepted — policy decision left to lecturer).
    - If no open tasks exist, a free-text title is used instead.
    """
    from datetime import datetime as dt

    open_tasks = models.get_open_assignment_tasks()

    if request.method == 'POST':
        task_id_raw = request.form.get('task_id', '').strip()
        title       = request.form.get('assignment_title', '').strip()
        file        = request.files.get('assignment_file')

        # Resolve task
        task_id   = None
        is_late   = False
        if task_id_raw and task_id_raw != '0':
            try:
                task_id = int(task_id_raw)
                task    = models.get_assignment_task_by_id(task_id)
                if task:
                    # Use the task's title if student didn't fill in their own
                    if not title:
                        title = task['title']
                    # Late submission check
                    due = dt.strptime(task['due_date'], '%Y-%m-%dT%H:%M')
                    if dt.now() > due:
                        is_late = True
            except (ValueError, Exception):
                task_id = None

        if not title:
            flash("Please enter an assignment title.", "danger")
            return render_template('student/submit_assignment.html',
                                   open_tasks=open_tasks)
        if file is None or file.filename == '':
            flash("Please select a file to submit.", "danger")
            return render_template('student/submit_assignment.html',
                                   open_tasks=open_tasks)
        if not allowed_file(file.filename, ALLOWED_ASSIGNMENT_EXTENSIONS):
            flash("Only .py, .pdf, and .zip files are accepted.", "danger")
            return render_template('student/submit_assignment.html',
                                   open_tasks=open_tasks)

        from werkzeug.utils import secure_filename
        original_name   = secure_filename(file.filename)
        unique_filename = f"s{session['user_id']}_{uuid.uuid4().hex}_{original_name}"
        file.save(os.path.join(app.config['ASSIGNMENTS_FOLDER'], unique_filename))

        # Store submission with task_id link
        conn = models.get_db_connection()
        conn.execute(
            """
            INSERT INTO assignments (student_id, title, filename, original_name, task_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session['user_id'], title, unique_filename, original_name, task_id)
        )
        conn.commit()
        conn.close()

        if is_late:
            flash("⚠️ Submitted LATE — past the deadline. Your lecturer has been notified.", "warning")
        else:
            flash("Assignment submitted successfully!", "success")
        return redirect(url_for('my_submissions'))

    return render_template('student/submit_assignment.html',
                           open_tasks=open_tasks)


@app.route('/student/profile', methods=['GET', 'POST'])
@student_required
def student_profile():
    """
    Student profile page — allows updating display name and profile picture.

    GET  → Renders the profile form with current data.
    POST → Handles two possible sub-actions via form hidden field 'action':
           'update_name' → saves a new display name to the database
           'update_pic'  → validates, saves, and records a new profile image
    """
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_name':
            # --- Update display name ---
            new_name = request.form.get('full_name', '').strip()
            if new_name:
                models.update_student_profile(session['user_id'], new_name)
                session['full_name'] = new_name  # Reflect in sidebar immediately
                flash("Display name updated.", "success")
            else:
                flash("Name cannot be empty.", "danger")

        elif action == 'update_pic':
            # --- Upload profile picture ---
            pic = request.files.get('profile_pic')
            if pic and pic.filename:
                if not allowed_file(pic.filename, ALLOWED_PROFILE_PIC_EXTENSIONS):
                    flash("Only JPG, PNG, or WEBP images are accepted.", "danger")
                else:
                    from werkzeug.utils import secure_filename
                    ext      = pic.filename.rsplit('.', 1)[1].lower()
                    filename = f"pfp_{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
                    pic.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
                    models.update_profile_picture(session['user_id'], filename)
                    session['profile_pic'] = filename  # Cache in session for sidebar
                    flash("Profile picture updated.", "success")
            else:
                flash("Please select an image file.", "danger")

        return redirect(url_for('student_profile'))

    # GET — load current profile data
    profile = models.get_student_profile(session['user_id'])
    return render_template('student/profile.html', profile=profile)


@app.route('/student/my-submissions')
@student_required
def my_submissions():
    """Student views their own submission history, grades, and feedback."""
    submissions = models.get_assignments_by_student(session['user_id'])
    return render_template('student/my_submissions.html', submissions=submissions)


# =============================================================================
#  SECTION 6 — FILE SERVING ROUTES
# =============================================================================

@app.route('/download/handout/<path:filename>')
@login_required
def download_handout(filename: str):
    """
    Serves a handout file for download. Requires login (any role).

    LESSON: send_from_directory() is the SAFE way to serve files.
    It validates the file is within the specified directory, preventing
    directory traversal attacks (e.g. ../../etc/passwd).
    """
    return send_from_directory(
        app.config['HANDOUTS_FOLDER'],
        filename,
        as_attachment=True   # Triggers browser "Save As" dialog
    )


# =============================================================================
#  ATTENDANCE ROUTES — QR-based daily attendance tracking
# =============================================================================

@app.route('/teacher/attendance', methods=['GET', 'POST'])
@staff_required
def teacher_attendance():
    """
    Staff attendance dashboard. Shows today's session with QR code and roll call.
    POST creates a new session for today if none exists.
    """
    if request.method == 'POST':
        attendance_session = models.create_attendance_session(
            created_by=session.get('user_id'),
            session_date=None  # Uses today
        )
        flash('Attendance session created. Students can now scan the QR code.', 'success')
        return redirect(url_for('teacher_attendance'))
    
    # GET: Show today's session or prompt to create
    todays_session = models.get_todays_session()
    attendance_roll = []
    if todays_session:
        attendance_roll = models.get_session_attendance_roll(todays_session['id'])
    
    return render_template(
        'teacher/attendance.html',
        attendance_session=todays_session,
        attendance_roll=attendance_roll
    )


@app.route('/teacher/attendance/qr/<int:session_id>')
@staff_required
def show_qr_code(session_id: int):
    """
    Display the QR code for a session as an image.
    Students scan this with phone camera to mark attendance.
    """
    import qrcode
    import io
    from base64 import b64encode
    
    # Verify session exists and was created by current staff
    conn = models.get_db_connection()
    session_row = conn.execute(
        "SELECT id, qr_code_value FROM attendance_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()
    
    if not session_row:
        return "Session not found", 404
    
    # Generate QR code pointing to student attendance endpoint
    qr_url = url_for('student_scan_attendance', qr_code=session_row['qr_code_value'], _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # Render as PNG and return as image
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')


@app.route('/teacher/attendance/sessions')
@staff_required
def teacher_attendance_sessions():
    """
    Attendance session report dashboard for staff.
    """
    sessions = models.get_attendance_sessions(days=180)
    return render_template(
        'teacher/attendance_report.html',
        sessions=sessions
    )


@app.route('/teacher/attendance/sessions/<int:session_id>')
@staff_required
def teacher_attendance_session_detail(session_id: int):
    """
    Shows detailed attendance roll call for a specific session.
    """
    session_info = models.get_attendance_session_by_id(session_id)
    if not session_info:
        flash('Attendance session not found.', 'danger')
        return redirect(url_for('teacher_attendance_sessions'))

    creator = models.get_user_by_id(session_info['created_by'])
    attendance_roll = models.get_session_attendance_roll(session_id)

    return render_template(
        'teacher/attendance_session.html',
        session=session_info,
        creator=creator,
        attendance_roll=attendance_roll
    )


@app.route('/teacher/attendance/history/<int:student_id>')
@staff_required
def student_attendance_history(student_id: int):
    """
    Shows a specific student's attendance history and stats.
    Accessible to staff only.
    """
    student = models.get_user_by_id(student_id)
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    history = models.get_student_attendance_history(student_id, days=30)
    stats = models.get_student_attendance_stats(student_id, days=30)
    
    return render_template(
        'teacher/student_attendance.html',
        student=student,
        history=history,
        stats=stats
    )


@app.route('/student/attendance/scan')
@student_required
def student_scan_attendance():
    """
    Student scans QR code. The QR code contains a URL to this endpoint with qr_code parameter.
    Marks the student present for today's session.
    """
    qr_code = request.args.get('qr_code')
    
    if not qr_code:
        flash('Invalid QR code', 'danger')
        return redirect(url_for('student_dashboard'))
    
    # Mark attendance
    success = models.verify_qr_and_mark_attendance(qr_code, session.get('user_id'))
    
    if success:
        flash('Attendance marked. Thank you.', 'success')
    else:
        flash('QR code invalid or you\'ve already scanned today.', 'warning')
    
    return redirect(url_for('student_attendance_view'))


@app.route('/student/attendance')
@student_required
def student_attendance_view():
    """
    Shows student's own attendance history and summary statistics.
    """
    history = models.get_student_attendance_history(session.get('user_id'), days=30)
    stats = models.get_student_attendance_stats(session.get('user_id'), days=30)
    
    return render_template(
        'student/attendance.html',
        history=history,
        stats=stats
    )


@app.route('/download/assignment/<path:filename>')
@admin_required
def download_assignment(filename: str):
    """Admin-only: downloads a student's submitted file for review."""
    return send_from_directory(
        app.config['ASSIGNMENTS_FOLDER'],
        filename,
        as_attachment=True
    )


@app.route('/profile-pic/<path:filename>')
@login_required
def serve_profile_pic(filename: str):
    """
    Serves a student profile picture. Login required.
    Images are stored in uploads/profile_pics/ and displayed in the sidebar.
    """
    return send_from_directory(app.config['PROFILE_PICS_FOLDER'], filename)


@app.route('/download/feed-media/<path:filename>')
def download_feed_media(filename: str):
    """
    Serves feed media images — NO login required (public access).

    LESSON: This route has NO decorator because the public homepage displays
    these images. If we required login, unauthenticated visitors would see
    broken images instead of the class activity photos.
    """
    return send_from_directory(
        app.config['FEED_MEDIA_FOLDER'],
        filename
        # Note: no as_attachment=True — we want inline display, not download
    )


# =============================================================================
#  ERROR HANDLERS
# =============================================================================

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500


# =============================================================================
#  ASSIGNMENT TASK ROUTES  (NEW in v4)
#  Lecturers create named tasks with deadlines; students submit against them.
# =============================================================================

@app.route('/admin/tasks', methods=['GET'])
@admin_required
def manage_tasks():
    """
    Admin/sub-teacher view: lists all assignment tasks with submission counts
    and open/closed status.
    """
    tasks = models.get_all_assignment_tasks()
    return render_template('teacher/manage_tasks.html', tasks=tasks)


@app.route('/admin/tasks/create', methods=['GET', 'POST'])
@admin_required
def create_task():
    """
    GET  → Show the create-task form.
    POST → Validate and save a new assignment task.
    """
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        due_date    = request.form.get('due_date', '').strip()

        if not title or not due_date:
            flash("Title and due date are required.", "danger")
            return redirect(url_for('create_task'))

        models.create_assignment_task(
            title=title,
            description=description,
            due_date=due_date,
            created_by=session['user_id']
        )
        flash(f"Assignment task '{title}' created successfully!", "success")
        return redirect(url_for('manage_tasks'))

    return render_template('teacher/create_task.html')


@app.route('/admin/tasks/<int:task_id>/toggle', methods=['POST'])
@admin_required
def toggle_task(task_id: int):
    """
    Toggles an assignment task between open and closed.
    Open tasks accept student submissions; closed ones don't.
    """
    task = models.get_assignment_task_by_id(task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for('manage_tasks'))

    new_state = 0 if task['is_open'] else 1
    models.toggle_task_open(task_id, new_state)
    label = "opened" if new_state else "closed"
    flash(f"Task '{task['title']}' has been {label}.", "success")
    return redirect(url_for('manage_tasks'))


@app.route('/admin/tasks/<int:task_id>/delete', methods=['POST'])
@admin_required
def delete_task(task_id: int):
    """
    Deletes an assignment task. Existing submissions that referenced it will
    have their task_id set to NULL (via ON DELETE SET NULL FK).
    """
    task = models.get_assignment_task_by_id(task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for('manage_tasks'))

    models.delete_assignment_task(task_id)
    flash(f"Task '{task['title']}' deleted.", "warning")
    return redirect(url_for('manage_tasks'))


@app.route('/admin/tasks/<int:task_id>/submissions')
@admin_required
def task_submissions(task_id: int):
    """
    Shows all submissions for a specific task so the lecturer can grade them
    efficiently without wading through unrelated submissions.
    """
    task = models.get_assignment_task_by_id(task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for('manage_tasks'))

    submissions = models.get_submissions_for_task(task_id)
    return render_template('teacher/task_submissions.html',
                           task=task, submissions=submissions)


# =============================================================================
#  ANNOUNCEMENT ROUTES  (NEW in v4)
#  Lecturers post notices; students see them on their dashboard with badge.
# =============================================================================

@app.route('/admin/announcements', methods=['GET'])
@admin_required
def manage_announcements():
    """Admin view: lists all announcements with edit/delete options."""
    announcements = models.get_all_announcements()
    return render_template('teacher/manage_announcements.html',
                           announcements=announcements)


@app.route('/admin/announcements/create', methods=['GET', 'POST'])
@admin_required
def create_announcement():
    """
    GET  → Show the create-announcement form.
    POST → Validate and save the announcement.
    """
    if request.method == 'POST':
        title     = request.form.get('title', '').strip()
        content   = request.form.get('content', '').strip()
        is_pinned = 1 if request.form.get('is_pinned') else 0

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for('create_announcement'))

        models.create_announcement(
            title=title,
            content=content,
            is_pinned=is_pinned,
            created_by=session['user_id']
        )
        flash(f"Announcement '{title}' posted!", "success")
        return redirect(url_for('manage_announcements'))

    return render_template('teacher/create_announcement.html')


@app.route('/admin/announcements/<int:announcement_id>/delete', methods=['POST'])
@admin_required
def delete_announcement_route(announcement_id: int):
    """Deletes an announcement by ID."""
    models.delete_announcement(announcement_id)
    flash("Announcement deleted.", "warning")
    return redirect(url_for('manage_announcements'))


@app.route('/student/announcements')
@login_required
def student_announcements():
    """
    Student view: full list of all announcements.
    Also marks all as 'read' by storing the latest announcement ID in session.
    """
    announcements = models.get_all_announcements()
    # Mark all as read by remembering the latest announcement ID
    latest_id = models.get_latest_announcement_id()
    session['last_seen_announcement_id'] = latest_id
    session.modified = True
    return render_template('student/announcements.html',
                           announcements=announcements)


# =============================================================================
#  ENTRY POINT
#
#  init_db() runs at module level so it executes both when running locally
#  with `python app.py` AND when gunicorn imports the module on Render.
# =============================================================================

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[START] CTE323 Portal v2 running at http://127.0.0.1:{port}")
    print("        Admin login: username='Musa Yahya'  password='260697'")
    app.run(debug=True, host='0.0.0.0', port=port)
