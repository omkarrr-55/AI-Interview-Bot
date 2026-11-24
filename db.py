"""
Skillverse SQLite Database Management Layer
Provides persistent storage for:
- Resumes (Drafts, custom templates & user data)
- AI Resume Audits (Audit history & ATS scores)
- Interview Question Generation History
- Dynamic Dashboard Statistics
"""

import os
import json
import sqlite3
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skillverse.db")


def get_db_connection(db_path=DB_FILE):
    """Establishes an SQLite connection with Row factory for dict-like access."""
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DB_FILE):
    """Initializes tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Resumes table (AI Resume Builder)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            template TEXT NOT NULL DEFAULT 'modern',
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Resume Audits table (AI Resume Analyzer)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            overall_score INTEGER NOT NULL,
            score_grade TEXT NOT NULL,
            ats_score INTEGER NOT NULL,
            ats_level TEXT NOT NULL,
            audit_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Question History table (Interview Question Generator)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            keywords TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Mock Interviews table (AI Mock Interview Simulator)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mock_interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            experience_level TEXT NOT NULL,
            interview_type TEXT NOT NULL,
            overall_score INTEGER NOT NULL,
            score_grade TEXT NOT NULL,
            summary_feedback TEXT NOT NULL,
            qa_history_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 5. ATS Resume Checks table (Phase 3 Dedicated ATS Checker)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ats_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            target_job_title TEXT DEFAULT '',
            ats_score INTEGER NOT NULL,
            ats_grade TEXT NOT NULL,
            format_score INTEGER NOT NULL,
            keyword_score INTEGER NOT NULL,
            section_score INTEGER NOT NULL,
            check_report_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. Platform Settings & Preferences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default platform settings if table is empty
    default_settings = [
        ("candidate_name", "Omkar"),
        ("candidate_email", ""),
        ("candidate_phone", ""),
        ("candidate_location", ""),
        ("target_role", "Full Stack Developer"),
        ("experience_level", "Mid-Level"),
        ("preferred_model", "llama-3.3-70b-versatile"),
        ("ai_rigor", "Balanced"),
        ("evaluation_temperature", "0.4"),
        ("auto_cleanup_uploads", "false"),
        ("theme_mode", "system"),
        ("font_size", "medium")
    ]
    cursor.executemany("INSERT OR IGNORE INTO platform_settings (key, value) VALUES (?, ?)", default_settings)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Resume Builder Operations
# ---------------------------------------------------------------------------

def save_resume(title, template, data_dict, resume_id=None, db_path=DB_FILE):
    """Inserts a new resume or updates an existing resume by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_str = json.dumps(data_dict, ensure_ascii=False)

    if resume_id:
        cursor.execute("""
            UPDATE resumes
            SET title = ?, template = ?, data_json = ?, updated_at = ?
            WHERE id = ?
        """, (title, template, data_str, now_str, resume_id))
        saved_id = resume_id
    else:
        cursor.execute("""
            INSERT INTO resumes (title, template, data_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (title, template, data_str, now_str, now_str))
        saved_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return saved_id


def get_resume(resume_id, db_path=DB_FILE):
    """Fetches a single resume by its ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "template": row["template"],
        "data": json.loads(row["data_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def list_resumes(limit=20, db_path=DB_FILE):
    """Lists recent resumes with parsed metadata."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, template, created_at, updated_at
        FROM resumes
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "template": r["template"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }
        for r in rows
    ]


def delete_resume(resume_id, db_path=DB_FILE):
    """Deletes a resume by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
# Resume Analyzer Audit Operations
# ---------------------------------------------------------------------------

def save_audit(filename, overall_score, score_grade, ats_score, ats_level, audit_dict, db_path=DB_FILE):
    """Records an audit report in the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    audit_str = json.dumps(audit_dict, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO resume_audits (filename, overall_score, score_grade, ats_score, ats_level, audit_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (filename, overall_score, score_grade, ats_score, ats_level, audit_str, now_str))

    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id


def get_recent_audits(limit=5, db_path=DB_FILE):
    """Fetches the most recent resume audit reports."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, overall_score, score_grade, ats_score, ats_level, created_at
        FROM resume_audits
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Interview Question History Operations
# ---------------------------------------------------------------------------

def save_question_history(filename, keywords, questions_list, db_path=DB_FILE):
    """Records a question generation session."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kw_str = ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
    q_str = json.dumps(questions_list, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO question_history (filename, keywords, questions_json, created_at)
        VALUES (?, ?, ?, ?)
    """, (filename, kw_str, q_str, now_str))

    qid = cursor.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_recent_questions(limit=5, db_path=DB_FILE):
    """Fetches recent interview question generation history."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, keywords, questions_json, created_at
        FROM question_history
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            d["questions"] = json.loads(d["questions_json"])
        except Exception:
            d["questions"] = []
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Mock Interview Operations (Phase 2 Simulator)
# ---------------------------------------------------------------------------

def save_mock_interview(role, experience_level, interview_type, overall_score, score_grade, summary_feedback, qa_history, db_path=DB_FILE):
    """Records a completed mock interview session and returns its ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qa_str = json.dumps(qa_history, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO mock_interviews (
            role, experience_level, interview_type, overall_score, score_grade, summary_feedback, qa_history_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (role, experience_level, interview_type, int(overall_score), score_grade, summary_feedback, qa_str, now_str))

    interview_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return interview_id


def get_mock_interview(interview_id, db_path=DB_FILE):
    """Fetches full details of a specific mock interview session."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_interviews WHERE id = ?", (interview_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    try:
        qa_history = json.loads(row["qa_history_json"])
    except Exception:
        qa_history = []

    return {
        "id": row["id"],
        "role": row["role"],
        "experience_level": row["experience_level"],
        "interview_type": row["interview_type"],
        "overall_score": row["overall_score"],
        "score_grade": row["score_grade"],
        "summary_feedback": row["summary_feedback"],
        "qa_history": qa_history,
        "created_at": row["created_at"]
    }


def list_mock_interviews(limit=20, db_path=DB_FILE):
    """Lists recent mock interview sessions for history view."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, role, experience_level, interview_type, overall_score, score_grade, summary_feedback, created_at
        FROM mock_interviews
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "role": r["role"],
            "experience_level": r["experience_level"],
            "interview_type": r["interview_type"],
            "overall_score": r["overall_score"],
            "score_grade": r["score_grade"],
            "summary_feedback": r["summary_feedback"],
            "created_at": r["created_at"]
        }
        for r in rows
    ]


def delete_mock_interview(interview_id, db_path=DB_FILE):
    """Deletes a mock interview record by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mock_interviews WHERE id = ?", (interview_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
# ATS Resume Checker Operations (Phase 3 Dedicated Module)
# ---------------------------------------------------------------------------

def save_ats_check(filename, target_job_title, ats_score, ats_grade,
                   format_score, keyword_score, section_score, check_report_dict, db_path=DB_FILE):
    """Records an ATS parsing simulation and audit report in SQLite."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_str = json.dumps(check_report_dict if isinstance(check_report_dict, dict) else {}, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO ats_checks (
            filename, target_job_title, ats_score, ats_grade,
            format_score, keyword_score, section_score, check_report_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        filename, target_job_title or "General Industry Benchmark",
        int(ats_score), ats_grade, int(format_score), int(keyword_score), int(section_score),
        report_str, now_str
    ))

    check_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return check_id


def get_ats_check(check_id, db_path=DB_FILE):
    """Fetches details of a specific ATS check report."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ats_checks WHERE id = ?", (check_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    try:
        report = json.loads(row["check_report_json"])
    except Exception:
        report = {}

    return {
        "id": row["id"],
        "filename": row["filename"],
        "target_job_title": row["target_job_title"],
        "ats_score": row["ats_score"],
        "ats_grade": row["ats_grade"],
        "format_score": row["format_score"],
        "keyword_score": row["keyword_score"],
        "section_score": row["section_score"],
        "report": report,
        "created_at": row["created_at"]
    }


def list_ats_checks(limit=20, db_path=DB_FILE):
    """Lists recent ATS checks with score summaries."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, target_job_title, ats_score, ats_grade,
               format_score, keyword_score, section_score, created_at
        FROM ats_checks
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "filename": r["filename"],
            "target_job_title": r["target_job_title"],
            "ats_score": r["ats_score"],
            "ats_grade": r["ats_grade"],
            "format_score": r["format_score"],
            "keyword_score": r["keyword_score"],
            "section_score": r["section_score"],
            "created_at": r["created_at"]
        }
        for r in rows
    ]


def delete_ats_check(check_id, db_path=DB_FILE):
    """Deletes an ATS check record by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ats_checks WHERE id = ?", (check_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
# Dashboard Analytics Summary
# ---------------------------------------------------------------------------

def get_dashboard_stats(db_path=DB_FILE):
    """Returns aggregated platform metrics for the Dashboard."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Total audits & average ATS score
    cursor.execute("SELECT COUNT(*), AVG(overall_score), AVG(ats_score) FROM resume_audits")
    audit_stats = cursor.fetchone()
    total_audits = audit_stats[0] if audit_stats else 0
    avg_score = round(audit_stats[1], 1) if audit_stats and audit_stats[1] is not None else 78.5
    avg_ats = round(audit_stats[2], 1) if audit_stats and audit_stats[2] is not None else 82.0

    # Total resumes created
    cursor.execute("SELECT COUNT(*) FROM resumes")
    total_resumes = cursor.fetchone()[0]

    # Total questions generated
    cursor.execute("SELECT COUNT(*) FROM question_history")
    total_questions = cursor.fetchone()[0]

    # Mock Interviews stats
    cursor.execute("SELECT COUNT(*), AVG(overall_score) FROM mock_interviews")
    interview_stats = cursor.fetchone()
    total_interviews = interview_stats[0] if interview_stats else 0
    avg_interview_score = round(interview_stats[1], 1) if interview_stats and interview_stats[1] is not None else 80.0

    # ATS Checks stats
    cursor.execute("SELECT COUNT(*), AVG(ats_score) FROM ats_checks")
    ats_stats = cursor.fetchone()
    total_ats_checks = ats_stats[0] if ats_stats else 0
    avg_ats_check_score = round(ats_stats[1], 1) if ats_stats and ats_stats[1] is not None else 80.0

    conn.close()

    return {
        "total_audits": total_audits,
        "avg_score": avg_score,
        "avg_ats": avg_ats,
        "total_resumes": total_resumes,
        "total_question_sets": total_questions,
        "total_interviews": total_interviews,
        "avg_interview_score": avg_interview_score,
        "total_ats_checks": total_ats_checks,
        "avg_ats_check_score": avg_ats_check_score
    }


# ---------------------------------------------------------------------------
# Platform Settings & Storage Management Operations
# ---------------------------------------------------------------------------

def get_setting(key, default=None, db_path=DB_FILE):
    """Retrieves a single configuration setting value by key."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM platform_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value, db_path=DB_FILE):
    """Inserts or updates a configuration setting value."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO platform_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, str(value), now_str))
    conn.commit()
    conn.close()
    return True


def get_all_settings(db_path=DB_FILE):
    """Returns all platform settings as a clean dictionary."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM platform_settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_storage_stats(db_path=DB_FILE):
    """Returns database size and detailed record counts for data management."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    db_size_kb = round(db_size_bytes / 1024, 1)

    cursor.execute("SELECT COUNT(*) FROM resumes")
    resumes_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM resume_audits")
    audits_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM question_history")
    questions_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM mock_interviews")
    interviews_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ats_checks")
    ats_count = cursor.fetchone()[0]

    conn.close()

    return {
        "db_size_kb": db_size_kb,
        "db_path": db_path,
        "resumes_count": resumes_count,
        "audits_count": audits_count,
        "questions_count": questions_count,
        "interviews_count": interviews_count,
        "ats_count": ats_count
    }


def clear_table_records(table_name, db_path=DB_FILE):
    """Safely clears history records from an authorized table."""
    allowed_tables = {"mock_interviews", "ats_checks", "question_history", "resume_audits"}
    if table_name not in allowed_tables:
        raise ValueError(f"Table '{table_name}' is not authorized for reset.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name}")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

