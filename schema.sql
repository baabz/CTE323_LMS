-- =============================================================================
--  schema.sql — CTE323 Course Portal Database Schema  (v2)
--  Kaduna Polytechnic | HND Computer Engineering
-- =============================================================================
--
--  WHAT CHANGED FROM v1:
--    • users.role now accepts 'admin', 'sub_teacher', 'student'
--      (old value 'teacher' is migrated to 'admin' automatically by init_db())
--    • users.full_name column added
--    • New 'public_feed' table for class activities / media posts
--
--  HOW MIGRATION WORKS:
--    If you have an existing portal.db from v1, init_db() in app.py will
--    detect the old schema and run an automatic migration — no data is lost.
--    New databases are created fresh with this schema.
-- =============================================================================


-- =============================================================================
--  TABLE: users
--  Now supports THREE roles:
--    'admin'       → Lead Lecturer — full system access
--    'sub_teacher' → Lab Assistant — handout upload + feed posting only
--    'student'     → Student       — view handouts, submit assignments
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('admin', 'sub_teacher', 'student')),
    --            ^ CHECK now has THREE valid values (was two in v1)
    full_name     TEXT,
    --            ^ NEW: display name, e.g. "Musa Ibrahim" or "Lab Assistant A"
    profile_picture TEXT,
    --            ^ NEW v3: filename of uploaded profile image (stored in uploads/profile_pics/)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);


-- =============================================================================
--  TABLE: handouts  (unchanged from v1)
-- =============================================================================
CREATE TABLE IF NOT EXISTS handouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    description   TEXT,
    filename      TEXT    NOT NULL UNIQUE,
    uploaded_by   INTEGER NOT NULL,
    uploaded_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
);


-- =============================================================================
--  TABLE: assignments  (unchanged from v1)
-- =============================================================================
CREATE TABLE IF NOT EXISTS assignments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL,
    title         TEXT    NOT NULL,
    filename      TEXT    NOT NULL UNIQUE,
    original_name TEXT    NOT NULL,
    submitted_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    grade         TEXT,
    feedback      TEXT,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);


-- =============================================================================
--  TABLE: public_feed  (NEW in v2)
--  Stores class activity posts visible to EVERYONE — even without login.
--
--  LESSON — Two types of media are supported:
--    media_type = 'image'      → media_path_or_url holds a local filename
--                                (file saved in uploads/feed_media/)
--    media_type = 'video_link' → media_path_or_url holds a YouTube URL string
--                                (e.g. https://www.youtube.com/watch?v=xxxxx)
--
--  Both admin and sub_teacher can INSERT into this table.
--  Only admin can DELETE from it.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public_feed (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    description       TEXT,
    media_type        TEXT    NOT NULL CHECK(media_type IN ('image', 'video_link')),
    --                ^ Exactly two allowed values — keeps data consistent
    media_path_or_url TEXT    NOT NULL,
    --                ^ Either a filename (image) or a full YouTube URL (video_link)
    uploaded_by       INTEGER NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
);


-- =============================================================================
--  TABLE: assignment_tasks  (NEW in v4)
--  Lecturer creates named assignment tasks with deadlines.
--  Students submit files AGAINST a specific task so submissions are organised.
--
--  LESSON: This is a one-to-many relationship:
--    One assignment_task → many assignments (submissions)
--    The FK in the assignments table will point here.
-- =============================================================================
CREATE TABLE IF NOT EXISTS assignment_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    description   TEXT,
    due_date      TEXT    NOT NULL,
    --            ^ Stored as ISO 8601 string: 'YYYY-MM-DD HH:MM'
    --              SQLite can compare and sort text dates in this format correctly.
    created_by    INTEGER NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    is_open       INTEGER NOT NULL DEFAULT 1,
    --            ^ 1 = accepting submissions, 0 = closed by lecturer
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);


-- =============================================================================
--  TABLE: announcements  (NEW in v4)
--  Lecturer posts notices visible to all students on their dashboard.
--  is_pinned = 1 keeps the announcement at the top of the list.
-- =============================================================================
CREATE TABLE IF NOT EXISTS announcements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    content       TEXT    NOT NULL,
    is_pinned     INTEGER NOT NULL DEFAULT 0,
    --            ^ 1 = pinned to top, 0 = normal order
    created_by    INTEGER NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================================================
--  TABLE: attendance_sessions  (NEW v5 — Attendance Feature)
--  Staff creates a daily attendance session. Each session gets a unique QR code.
--  Students scan the QR to mark themselves present for the day.
-- =============================================================================
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date  TEXT    NOT NULL,
    --            ^ YYYY-MM-DD format (one session per day)
    created_by    INTEGER NOT NULL,
    --            ^ user id of staff who created this session
    qr_code_value TEXT    UNIQUE NOT NULL,
    --            ^ unique identifier for QR (UUID format)
    expires_at    TEXT,
    --            ^ optional expiry time for the QR session
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================================================
--  TABLE: attendance_records  (NEW v5)
--  One record per student per session (UNIQUE constraint enforces this).
--  Tracks who scanned the QR code and when.
-- =============================================================================
CREATE TABLE IF NOT EXISTS attendance_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    student_id    INTEGER NOT NULL,
    scanned_at    TEXT    NOT NULL,
    --            ^ ISO datetime when QR was scanned
    marked_present INTEGER NOT NULL DEFAULT 1,
    --            ^ 1 = present (scanned), 0 = absent (staff marked manually)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(session_id, student_id)
    --            ^ enforces one record per student per session
);
