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

    conn.close()

    return {
        "total_audits": total_audits,
        "avg_score": avg_score,
        "avg_ats": avg_ats,
        "total_resumes": total_resumes,
        "total_question_sets": total_questions,
        "total_interviews": total_interviews,
        "avg_interview_score": avg_interview_score
    }
