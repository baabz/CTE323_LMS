# =============================================================================
#  models.py — Database Helper Functions
#  CTE323 Course Portal | Kaduna Polytechnic
# =============================================================================
#
#  LESSON: This file contains ONLY functions that talk to the database.
#  Separating database logic from route logic (in app.py) is called the
#  "separation of concerns" principle — a key concept in software engineering.
#
#  IMPORTANT: We use Python's built-in 'sqlite3' module — no third-party ORM.
#  Every SQL query is written out explicitly as a string so you can read it,
#  copy it, and run it directly in the SQLite shell to understand what it does.
#
#  HOW sqlite3 WORKS (quick summary):
#    1. sqlite3.connect(DB_PATH)  → opens/creates the database file
#    2. conn.cursor()             → creates a cursor (our "pen" to write SQL)
#    3. cursor.execute(sql, args) → runs the SQL query
#    4. conn.commit()             → saves INSERT/UPDATE/DELETE changes
#    5. conn.close()              → closes the file handle (always do this!)
#
#  v2 ADDITIONS (new in this version):
#    Section 5 — Public Feed functions
#    Section 6 — Staff Management functions (Admin only)
# =============================================================================

import sqlite3      # Built-in Python module — no pip install needed
import hashlib      # Built-in module for hashing passwords
import os           # For building file paths

# -----------------------------------------------------------------------------
#  Database path — one central place so every function finds the same file.
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Folder where models.py lives
DB_PATH  = os.path.join(BASE_DIR, 'portal.db')          # Full path to our SQLite file


# =============================================================================
#  UTILITY: get_db_connection()
# =============================================================================
def get_db_connection():
    """
    Opens a connection to the SQLite database and returns it.

    WHY row_factory?
        Without it:  row[0], row[1], row[2]  <- hard to read!
        With it:     row['username'], row['role']  <- clear and self-documenting
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # Enable column-name access on rows
    conn.execute("PRAGMA foreign_keys = ON")   # Enforce FK constraints (off by default!)
    return conn


# =============================================================================
#  UTILITY: hash_password(plain_text_password)
#  LESSON: NEVER store passwords as plain text in a database.
#  We use SHA-256 — a one-way function. You can hash "hello" -> "2cf24d...",
#  but you CANNOT reverse it. At login, we hash the typed password and compare.
# =============================================================================
def hash_password(plain_text: str) -> str:
    """
    Returns the SHA-256 hex digest of a plain-text password string.

    Example:
        hash_password("MySecret") -> "a0f4c2..."
    """
    return hashlib.sha256(plain_text.encode('utf-8')).hexdigest()


# =============================================================================
#  LESSON BLOCK: SQL PLACEHOLDERS
#  NEVER use Python f-strings to insert user data into SQL — that causes
#  SQL Injection attacks!
#
#  BAD  (vulnerable): f"SELECT * FROM users WHERE username = '{name}'"
#  GOOD (safe):       "SELECT * FROM users WHERE username = ?", (name,)
#
#  The '?' placeholder tells sqlite3 to safely escape the value for you.
# =============================================================================


# =============================================================================
#  SECTION 1 — USER FUNCTIONS
# =============================================================================

def create_user(username: str, password: str, role: str) -> bool:
    """
    Inserts a new user into the 'users' table (students only via public form).

    SQL USED:
        INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)

    Returns True if successful, False if username already exists.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # IntegrityError raised when UNIQUE constraint is violated (duplicate username)
        return False
    finally:
        conn.close()    # Always close the connection — good habit!


def get_user_by_username(username: str):
    """
    Fetches a single user row by their username.

    SQL USED:
        SELECT * FROM users WHERE username = ?

    Returns a sqlite3.Row object (or None if not found).
    """
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)   # Note the trailing comma — this makes it a TUPLE, not just parentheses
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id: int):
    """
    Fetches a single user row by their primary key ID.

    SQL USED:
        SELECT * FROM users WHERE id = ?
    """
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


def get_all_students():
    """
    Returns a list of all users with role = 'student'.

    SQL USED:
        SELECT * FROM users WHERE role = 'student' ORDER BY username ASC
    """
    conn = get_db_connection()
    students = conn.execute(
        "SELECT * FROM users WHERE role = 'student' ORDER BY username ASC"
    ).fetchall()
    conn.close()
    return students


def verify_login(username: str, password: str):
    """
    Checks if the username/password combination is valid.

    Returns the user Row if valid, or None if invalid.
    """
    user = get_user_by_username(username)
    if user is None:
        return None   # User doesn't exist at all

    if user['password_hash'] == hash_password(password):
        return user   # Login valid — return the user object
    return None       # Password incorrect


# =============================================================================
#  SECTION 2 — HANDOUT FUNCTIONS
# =============================================================================

def add_handout(title: str, description: str, filename: str, uploaded_by: int) -> int:
    """
    Inserts a new handout record and returns its new ID.

    SQL USED:
        INSERT INTO handouts (title, description, filename, uploaded_by)
        VALUES (?, ?, ?, ?)
    """
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO handouts (title, description, filename, uploaded_by) VALUES (?, ?, ?, ?)",
        (title, description, filename, uploaded_by)
    )
    conn.commit()
    new_id = cursor.lastrowid   # .lastrowid gives us the auto-generated primary key
    conn.close()
    return new_id


def get_all_handouts():
    """
    Fetches all handouts along with the uploader's username (via JOIN).

    SQL USED:
        SELECT h.*, u.username AS uploader_name
        FROM handouts h
        JOIN users u ON h.uploaded_by = u.id
        ORDER BY h.uploaded_at DESC

    LESSON: JOIN combines rows from two tables where a condition is met.
    """
    conn = get_db_connection()
    handouts = conn.execute(
        """
        SELECT h.id,
               h.title,
               h.description,
               h.filename,
               h.uploaded_at,
               u.username AS uploader_name
        FROM   handouts h
        JOIN   users    u  ON h.uploaded_by = u.id
        ORDER  BY h.uploaded_at DESC
        """
    ).fetchall()
    conn.close()
    return handouts


def get_handout_by_id(handout_id: int):
    """
    Returns a single handout row by its ID.

    SQL USED:
        SELECT * FROM handouts WHERE id = ?
    """
    conn = get_db_connection()
    handout = conn.execute(
        "SELECT * FROM handouts WHERE id = ?",
        (handout_id,)
    ).fetchone()
    conn.close()
    return handout


def delete_handout(handout_id: int):
    """
    Removes a handout record from the database.

    SQL USED:
        DELETE FROM handouts WHERE id = ?

    NOTE: The actual file on disk must be deleted separately in the route.
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM handouts WHERE id = ?", (handout_id,))
    conn.commit()
    conn.close()


# =============================================================================
#  SECTION 3 — ASSIGNMENT FUNCTIONS
# =============================================================================

def submit_assignment(student_id: int, title: str, filename: str, original_name: str) -> int:
    """
    Inserts a new assignment submission record and returns its new ID.

    SQL USED:
        INSERT INTO assignments (student_id, title, filename, original_name)
        VALUES (?, ?, ?, ?)
    """
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO assignments (student_id, title, filename, original_name) VALUES (?, ?, ?, ?)",
        (student_id, title, filename, original_name)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_assignments_by_student(student_id: int):
    """
    Returns all assignment submissions for a specific student,
    including the task's due_date (if linked) for late/on-time display.

    SQL USED:
        SELECT a.*, t.due_date AS task_due_date, t.title AS task_title
        FROM   assignments a
        LEFT JOIN assignment_tasks t ON a.task_id = t.id
        WHERE  a.student_id = ?
        ORDER  BY a.submitted_at DESC
    """
    conn = get_db_connection()
    assignments = conn.execute(
        """
        SELECT a.*,
               t.due_date  AS task_due_date,
               t.title     AS task_title
        FROM   assignments       a
        LEFT JOIN assignment_tasks t ON a.task_id = t.id
        WHERE  a.student_id = ?
        ORDER  BY a.submitted_at DESC
        """,
        (student_id,)
    ).fetchall()
    conn.close()
    return assignments


def get_all_assignments():
    """
    Returns ALL submissions across all students, with student usernames (via JOIN).

    SQL USED:
        SELECT a.*, u.username AS student_name
        FROM assignments a
        JOIN users u ON a.student_id = u.id
        ORDER BY a.submitted_at DESC
    """
    conn = get_db_connection()
    assignments = conn.execute(
        """
        SELECT a.id,
               a.title,
               a.filename,
               a.original_name,
               a.submitted_at,
               a.grade,
               a.feedback,
               u.username AS student_name
        FROM   assignments a
        JOIN   users       u  ON a.student_id = u.id
        ORDER  BY a.submitted_at DESC
        """
    ).fetchall()
    conn.close()
    return assignments


def get_assignment_by_id(assignment_id: int):
    """
    Returns a single assignment row by its ID (with student username via JOIN).
    """
    conn = get_db_connection()
    assignment = conn.execute(
        """
        SELECT a.*,
               u.username AS student_name
        FROM   assignments a
        JOIN   users       u  ON a.student_id = u.id
        WHERE  a.id = ?
        """,
        (assignment_id,)
    ).fetchone()
    conn.close()
    return assignment


def grade_assignment(assignment_id: int, grade: str, feedback: str):
    """
    Updates the grade and feedback for a submitted assignment.

    SQL USED:
        UPDATE assignments SET grade = ?, feedback = ? WHERE id = ?

    LESSON: Without the WHERE clause, ALL rows in the table would be updated!
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE assignments SET grade = ?, feedback = ? WHERE id = ?",
        (grade, feedback, assignment_id)
    )
    conn.commit()
    conn.close()


# =============================================================================
#  SECTION 4 — STATISTICS
#  LESSON: SQL aggregate functions COUNT(), used to build dashboard summaries.
# =============================================================================

def get_dashboard_stats() -> dict:
    """
    Returns a dict of summary statistics for the admin dashboard.

    SQL USED:
        COUNT(*) — counts ALL rows in a result set
        COUNT(*) WHERE role = '...' — filtered count
    """
    conn = get_db_connection()

    # Each query returns a single-row, single-column result.
    # .fetchone()[0] extracts just that integer value.
    student_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]

    sub_teacher_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'sub_teacher'"
    ).fetchone()[0]

    handout_count = conn.execute(
        "SELECT COUNT(*) FROM handouts"
    ).fetchone()[0]

    submission_count = conn.execute(
        "SELECT COUNT(*) FROM assignments"
    ).fetchone()[0]

    graded_count = conn.execute(
        "SELECT COUNT(*) FROM assignments WHERE grade IS NOT NULL AND grade != ''"
    ).fetchone()[0]

    # NEW: Count public feed posts
    feed_count = conn.execute(
        "SELECT COUNT(*) FROM public_feed"
    ).fetchone()[0]

    conn.close()

    return {
        'student_count':     student_count,
        'sub_teacher_count': sub_teacher_count,
        'handout_count':     handout_count,
        'submission_count':  submission_count,
        'graded_count':      graded_count,
        'pending_count':     submission_count - graded_count,
        'feed_count':        feed_count,
    }


# =============================================================================
#  SECTION 5 — PUBLIC FEED FUNCTIONS  (NEW in v2)
#  These functions manage the 'public_feed' table — visible to everyone,
#  even unauthenticated visitors on the homepage.
# =============================================================================

def add_feed_post(title: str, description: str, media_type: str,
                  media_path_or_url: str, uploaded_by: int) -> int:
    """
    Inserts a new post into the public_feed table.

    SQL USED:
        INSERT INTO public_feed (title, description, media_type, media_path_or_url, uploaded_by)
        VALUES (?, ?, ?, ?, ?)

    PARAMETERS:
        media_type        — 'image' or 'video_link'
        media_path_or_url — saved filename (for images) OR full YouTube URL (for videos)
        uploaded_by       — user ID of the admin or sub_teacher posting

    Returns the newly created post's ID.
    """
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO public_feed (title, description, media_type, media_path_or_url, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, description, media_type, media_path_or_url, uploaded_by)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_feed_posts():
    """
    Fetches ALL public feed posts, newest first, with poster details via JOIN.

    SQL USED:
        SELECT f.*, u.username AS uploader_name, u.full_name AS uploader_fullname
        FROM public_feed f
        JOIN users u ON f.uploaded_by = u.id
        ORDER BY f.created_at DESC

    LESSON: This is the core query for the public homepage.
    Anyone — logged in or not — triggers this SELECT when they visit '/'.
    """
    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT f.id,
               f.title,
               f.description,
               f.media_type,
               f.media_path_or_url,
               f.created_at,
               u.username         AS uploader_name,
               u.full_name        AS uploader_fullname
        FROM   public_feed f
        JOIN   users        u  ON f.uploaded_by = u.id
        ORDER  BY f.created_at DESC
        """
    ).fetchall()
    conn.close()
    return posts


def get_feed_post_by_id(post_id: int):
    """
    Returns a single public_feed row by ID (used before delete operations).

    SQL USED:
        SELECT * FROM public_feed WHERE id = ?
    """
    conn = get_db_connection()
    post = conn.execute(
        "SELECT * FROM public_feed WHERE id = ?",
        (post_id,)
    ).fetchone()
    conn.close()
    return post


def delete_feed_post(post_id: int):
    """
    Deletes a feed post record from the database (admin only).

    SQL USED:
        DELETE FROM public_feed WHERE id = ?

    NOTE: If the post has an image file, the caller must delete it from disk too.
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM public_feed WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()


# =============================================================================
#  SECTION 6 — STAFF MANAGEMENT FUNCTIONS  (NEW in v2, Admin only)
#  These functions allow the admin to view existing staff and create
#  new sub_teacher accounts without exposing the public /register page.
# =============================================================================

def get_all_staff():
    """
    Returns all users with role 'admin' or 'sub_teacher'.

    SQL USED:
        SELECT * FROM users
        WHERE role IN ('admin', 'sub_teacher')
        ORDER BY role, username ASC

    LESSON: The IN operator matches against a set of values — equivalent to
    writing: WHERE role = 'admin' OR role = 'sub_teacher'
    """
    conn = get_db_connection()
    staff = conn.execute(
        """
        SELECT id, username, full_name, role, created_at
        FROM   users
        WHERE  role IN ('admin', 'sub_teacher')
        ORDER  BY role ASC, username ASC
        """
    ).fetchall()
    conn.close()
    return staff


def create_staff_user(username: str, password: str, full_name: str, role: str) -> bool:
    """
    Creates a new staff account (admin or sub_teacher). Admin-only action.

    SQL USED:
        INSERT INTO users (username, password_hash, role, full_name)
        VALUES (?, ?, ?, ?)

    Returns True on success, False if username already exists.

    NOTE: This is separate from create_user() because staff accounts include
    a full_name and their role is set explicitly by the admin — not by a
    public registration form.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, full_name)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# =============================================================================
#  SECTION 7 — PROFILE MANAGEMENT FUNCTIONS  (NEW in v3)
# =============================================================================

def update_profile_picture(user_id: int, filename: str):
    """
    Updates the profile_picture column for a user.

    SQL USED:
        UPDATE users SET profile_picture = ? WHERE id = ?
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET profile_picture = ? WHERE id = ?",
        (filename, user_id)
    )
    conn.commit()
    conn.close()


def update_student_profile(user_id: int, full_name: str):
    """
    Updates the student's display name.

    SQL USED:
        UPDATE users SET full_name = ? WHERE id = ?
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET full_name = ? WHERE id = ?",
        (full_name, user_id)
    )
    conn.commit()
    conn.close()


def get_student_profile(user_id: int):
    """
    Returns a user's full profile including profile picture path.

    SQL USED:
        SELECT id, username, full_name, role, profile_picture, created_at
        FROM users WHERE id = ?
    """
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, full_name, role, profile_picture, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


# =============================================================================
#  SECTION 8 — ASSIGNMENT TASK FUNCTIONS  (NEW in v4)
#  Lecturer creates named tasks with deadlines; students submit against them.
# =============================================================================

def create_assignment_task(title: str, description: str, due_date: str,
                           created_by: int) -> int:
    """
    Inserts a new assignment task record and returns its ID.

    SQL USED:
        INSERT INTO assignment_tasks (title, description, due_date, created_by)
        VALUES (?, ?, ?, ?)
    """
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO assignment_tasks (title, description, due_date, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (title, description, due_date, created_by)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_assignment_tasks():
    """
    Returns all assignment tasks, newest first, with creator's name.

    SQL USED:
        SELECT t.*, u.username AS creator_name
        FROM assignment_tasks t
        JOIN users u ON t.created_by = u.id
        ORDER BY t.due_date ASC
    """
    conn = get_db_connection()
    tasks = conn.execute(
        """
        SELECT t.id, t.title, t.description, t.due_date,
               t.is_open, t.created_at,
               u.username AS creator_name,
               COUNT(a.id) AS submission_count
        FROM   assignment_tasks t
        JOIN   users u ON t.created_by = u.id
        LEFT JOIN assignments a ON a.task_id = t.id
        GROUP BY t.id
        ORDER BY t.due_date ASC
        """
    ).fetchall()
    conn.close()
    return tasks


def get_assignment_task_by_id(task_id: int):
    """Returns a single assignment task by ID."""
    conn = get_db_connection()
    task = conn.execute(
        "SELECT * FROM assignment_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    conn.close()
    return task


def get_open_assignment_tasks():
    """
    Returns only open tasks (is_open=1) ordered by nearest deadline.
    Used on the student submission form.
    """
    conn = get_db_connection()
    tasks = conn.execute(
        """
        SELECT * FROM assignment_tasks
        WHERE is_open = 1
        ORDER BY due_date ASC
        """
    ).fetchall()
    conn.close()
    return tasks


def toggle_task_open(task_id: int, is_open: int):
    """Opens (1) or closes (0) an assignment task for submissions."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE assignment_tasks SET is_open = ? WHERE id = ?",
        (is_open, task_id)
    )
    conn.commit()
    conn.close()


def delete_assignment_task(task_id: int):
    """
    Deletes an assignment task record.

    NOTE: Submissions that referenced this task will have their task_id
    set to NULL automatically (handled by the ON DELETE SET NULL FK below).
    The actual files on disk must be deleted separately.

    SQL USED:
        DELETE FROM assignment_tasks WHERE id = ?
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM assignment_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_submissions_for_task(task_id: int):
    """
    Returns all student submissions for a specific task, with student username.

    SQL USED:
        SELECT a.*, u.username AS student_name
        FROM assignments a
        JOIN users u ON a.student_id = u.id
        WHERE a.task_id = ?
        ORDER BY a.submitted_at ASC
    """
    conn = get_db_connection()
    subs = conn.execute(
        """
        SELECT a.id, a.title, a.filename, a.original_name,
               a.submitted_at, a.grade, a.feedback, a.task_id,
               u.username AS student_name
        FROM   assignments a
        JOIN   users u ON a.student_id = u.id
        WHERE  a.task_id = ?
        ORDER  BY a.submitted_at ASC
        """,
        (task_id,)
    ).fetchall()
    conn.close()
    return subs


# =============================================================================
#  SECTION 9 — ANNOUNCEMENT FUNCTIONS  (NEW in v4)
#  Lecturer posts notices; students see them on their dashboard.
# =============================================================================

def create_announcement(title: str, content: str, is_pinned: int,
                        created_by: int) -> int:
    """
    Inserts a new announcement and returns its new ID.

    SQL USED:
        INSERT INTO announcements (title, content, is_pinned, created_by)
        VALUES (?, ?, ?, ?)
    """
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO announcements (title, content, is_pinned, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (title, content, is_pinned, created_by)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_announcements():
    """
    Returns all announcements: pinned ones first, then newest first.

    SQL USED:
        ORDER BY is_pinned DESC, created_at DESC
    """
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT a.id, a.title, a.content, a.is_pinned, a.created_at,
               u.username AS poster_name,
               u.full_name AS poster_fullname
        FROM   announcements a
        JOIN   users u ON a.created_by = u.id
        ORDER  BY a.is_pinned DESC, a.created_at DESC
        """
    ).fetchall()
    conn.close()
    return rows


def get_latest_announcement_id() -> int:
    """
    Returns the ID of the most recently created announcement (or 0 if none).
    Used to compute the unread badge count in the sidebar.
    """
    conn = get_db_connection()
    row = conn.execute(
        "SELECT MAX(id) FROM announcements"
    ).fetchone()
    conn.close()
    return row[0] or 0


def delete_announcement(announcement_id: int):
    """
    Deletes an announcement by ID.

    SQL USED:
        DELETE FROM announcements WHERE id = ?
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()


# =============================================================================
#  SECTION 10 — ATTENDANCE FUNCTIONS  (NEW v5 — QR-Based Daily Attendance)
#  Staff records attendance by generating QR codes; students scan to mark present.
# =============================================================================

import uuid
from datetime import datetime, timedelta


def create_attendance_session(created_by: int, session_date: str = None) -> dict:
    """
    Creates a new attendance session for a given date.
    Generates a unique QR code value (UUID).
    
    Args:
        created_by: User ID of the staff member creating the session
        session_date: Date string 'YYYY-MM-DD'. If None, uses today's date.
    
    Returns:
        Dict with keys: id, session_date, qr_code_value, created_by, created_at
    
    SQL USED:
        INSERT INTO attendance_sessions (session_date, created_by, qr_code_value)
        VALUES (?, ?, ?)
    """
    if session_date is None:
        session_date = datetime.now().strftime('%Y-%m-%d')
    
    qr_code = str(uuid.uuid4())  # Unique identifier for this session
    
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO attendance_sessions (session_date, created_by, qr_code_value)
        VALUES (?, ?, ?)
        """,
        (session_date, created_by, qr_code)
    )
    session_id = cursor.lastrowid
    conn.commit()
    
    session = conn.execute(
        "SELECT id, session_date, qr_code_value, created_by, created_at FROM attendance_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()
    return session


def get_todays_session() -> dict:
    """
    Returns today's attendance session if it exists, otherwise None.
    
    SQL USED:
        SELECT id, session_date, qr_code_value, created_by, created_at
        FROM attendance_sessions
        WHERE session_date = ?
        LIMIT 1
    """
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    session = conn.execute(
        """
        SELECT id, session_date, qr_code_value, created_by, created_at
        FROM attendance_sessions
        WHERE session_date = ?
        LIMIT 1
        """,
        (today,)
    ).fetchone()
    conn.close()
    return session


def get_attendance_sessions(days: int = 90) -> list:
    """
    Returns recent attendance sessions with scan counts and creator info.
    """
    conn = get_db_connection()
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    sessions = conn.execute(
        """
        SELECT
            s.id,
            s.session_date,
            s.created_by,
            s.qr_code_value,
            s.created_at,
            u.full_name AS created_by_name,
            COUNT(ar.id) AS scanned_count
        FROM attendance_sessions s
        LEFT JOIN attendance_records ar ON ar.session_id = s.id
        LEFT JOIN users u ON s.created_by = u.id
        WHERE s.session_date >= ?
        GROUP BY s.id
        ORDER BY s.session_date DESC, s.created_at DESC
        """,
        (cutoff_date,)
    ).fetchall()
    conn.close()
    return sessions


def get_attendance_session_by_id(session_id: int) -> dict:
    """
    Returns a single attendance session by its ID.
    """
    conn = get_db_connection()
    session = conn.execute(
        "SELECT id, session_date, qr_code_value, created_by, created_at FROM attendance_sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()
    return session


def verify_qr_and_mark_attendance(qr_code: str, student_id: int) -> bool:
    """
    Verifies the QR code is valid (exists in today's session) and marks the student present.
    
    Returns:
        True if successfully marked, False if QR invalid or student already marked.
    
    SQL USED:
        SELECT id FROM attendance_sessions WHERE qr_code_value = ? AND session_date = ?
        INSERT INTO attendance_records (session_id, student_id, scanned_at, marked_present)
        VALUES (?, ?, ?, 1)
    """
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Find the session with this QR code (must be today)
    session = conn.execute(
        "SELECT id FROM attendance_sessions WHERE qr_code_value = ? AND session_date = ?",
        (qr_code, today)
    ).fetchone()
    
    if not session:
        conn.close()
        return False
    
    session_id = session['id']
    now = datetime.now().isoformat()
    
    try:
        conn.execute(
            """
            INSERT INTO attendance_records (session_id, student_id, scanned_at, marked_present)
            VALUES (?, ?, ?, 1)
            """,
            (session_id, student_id, now)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        # Student already marked for this session (UNIQUE constraint violation)
        conn.close()
        return False


def get_session_attendance_roll(session_id: int) -> list:
    """
    Returns all attendance records for a given session.
    Shows who attended with scan time.
    
    SQL USED:
        SELECT ar.id, ar.student_id, u.full_name, u.username, ar.scanned_at, ar.marked_present
        FROM attendance_records ar
        JOIN users u ON ar.student_id = u.id
        WHERE ar.session_id = ?
        ORDER BY ar.scanned_at ASC
    """
    conn = get_db_connection()
    records = conn.execute(
        """
        SELECT ar.id, ar.student_id, u.full_name, u.username, ar.scanned_at, ar.marked_present
        FROM attendance_records ar
        JOIN users u ON ar.student_id = u.id
        WHERE ar.session_id = ?
        ORDER BY ar.scanned_at ASC
        """,
        (session_id,)
    ).fetchall()
    conn.close()
    return records


def get_student_attendance_history(student_id: int, days: int = 30) -> list:
    """
    Returns student's attendance records for the last N days.
    Includes session date and attendance status.
    
    SQL USED:
        SELECT ash.session_date, ar.marked_present, ar.scanned_at
        FROM attendance_records ar
        JOIN attendance_sessions ash ON ar.session_id = ash.id
        WHERE ar.student_id = ?
        AND ash.session_date >= DATE('now', 'localtime', '-30 days')
        ORDER BY ash.session_date DESC
    """
    conn = get_db_connection()
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    records = conn.execute(
        """
        SELECT ash.session_date, ar.marked_present, ar.scanned_at
        FROM attendance_records ar
        JOIN attendance_sessions ash ON ar.session_id = ash.id
        WHERE ar.student_id = ?
        AND ash.session_date >= ?
        ORDER BY ash.session_date DESC
        """,
        (student_id, cutoff_date)
    ).fetchall()
    conn.close()
    return records


def get_student_attendance_stats(student_id: int, days: int = 30) -> dict:
    """
    Returns attendance statistics for a student.
    
    Returns:
        Dict with: total_sessions, attended, absent, percentage, period_days
    
    SQL USED:
        SELECT COUNT(*) as total_sessions,
               SUM(marked_present) as attended
        FROM attendance_records ar
        JOIN attendance_sessions ash ON ar.session_id = ash.id
        WHERE ar.student_id = ?
        AND ash.session_date >= ?
    """
    conn = get_db_connection()
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    row = conn.execute(
        """
        SELECT COUNT(*) as total_sessions,
               SUM(CASE WHEN marked_present = 1 THEN 1 ELSE 0 END) as attended
        FROM attendance_records ar
        JOIN attendance_sessions ash ON ar.session_id = ash.id
        WHERE ar.student_id = ?
        AND ash.session_date >= ?
        """,
        (student_id, cutoff_date)
    ).fetchone()
    conn.close()
    
    total = row['total_sessions'] or 0
    attended = row['attended'] or 0
    absent = total - attended
    percentage = round((attended / total * 100) if total > 0 else 0, 1)
    
    return {
        'total_sessions': total,
        'attended': attended,
        'absent': absent,
        'percentage': percentage,
        'period_days': days
    }


def manually_mark_attendance(session_id: int, student_id: int, marked_present: bool):
    """
    Staff manually marks a student present or absent for a session.
    
    SQL USED:
        INSERT OR REPLACE INTO attendance_records (session_id, student_id, scanned_at, marked_present)
        VALUES (?, ?, ?, ?)
    """
    conn = get_db_connection()
    now = datetime.now().isoformat()
    
    conn.execute(
        """
        INSERT OR REPLACE INTO attendance_records (session_id, student_id, scanned_at, marked_present)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, student_id, now, 1 if marked_present else 0)
    )
    conn.commit()
    conn.close()


def get_all_students() -> list:
    """
    Returns all student users (for staff to select when manually marking attendance).
    
    SQL USED:
        SELECT id, username, full_name FROM users WHERE role = 'student' ORDER BY full_name ASC
    """
    conn = get_db_connection()
    students = conn.execute(
        "SELECT id, username, full_name FROM users WHERE role = 'student' ORDER BY full_name ASC"
    ).fetchall()
    conn.close()
    return students
