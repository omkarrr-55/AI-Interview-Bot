from datetime import datetime
import os
import uuid
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from groq import Groq
from resume_parser import extract_keywords
from question_generator import generate_questions
from resume_analyzer import analyze_resume_file
from db import (
    init_db, save_resume, get_resume, list_resumes, delete_resume,
    save_audit, get_recent_audits,
    save_question_history, get_recent_questions,
    save_mock_interview, get_mock_interview, list_mock_interviews, delete_mock_interview,
    save_ats_check, get_ats_check, list_ats_checks, delete_ats_check,
    get_setting, set_setting, get_all_settings, get_storage_stats, clear_table_records,
    get_dashboard_stats
)
from resume_builder import (
    generate_summary, improve_bullet, generate_project_description, get_action_verbs
)
from interview_simulator import (
    generate_interview_questions, evaluate_answer, compile_final_report
)
from ats_checker import audit_resume_for_ats

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'skillverse-secret-key-2026-omkar')
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Initialize SQLite database tables
init_db()

def process_resume_upload(req):
    """Safely extracts keywords from an uploaded resume and generates interview questions."""
    questions = None
    error = None
    if 'resume' not in req.files or req.files['resume'].filename == '':
        error = "Please upload a valid .pdf or .docx resume file."
        return questions, error

    file = req.files['resume']
    filename = secure_filename(file.filename)
    if not filename:
        error = "Invalid filename. Please select a valid document."
        return questions, error

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(filepath)
        # Extract keywords from resume
        keywords = extract_keywords(filepath)
        if not keywords:
            error = "Could not extract readable skills from the resume. Please check your document."
            return questions, error

        # Generate questions using Groq
        questions = generate_questions(keywords)
        if not questions:
            error = "Could not generate questions. Please ensure your Groq API key is valid and configured."
        else:
            # Persist question set to SQLite database
            try:
                save_question_history(filename, keywords, questions)
            except Exception:
                pass
    except Exception as e:
        error = f"Error processing resume: {str(e)}"

    return questions, error


# ---------------------------------------------------------------------------
# Core Routes
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main entry point. Serves the dashboard on GET, handles question generation on POST."""
    if request.method == 'POST':
        questions, error = process_resume_upload(request)
        return render_template(
            'question_generator.html',
            questions=questions,
            error=error,
            active_page='question_generator',
            now=datetime.now()
        )
    stats = get_dashboard_stats()
    recent_audits = get_recent_audits(5)
    recent_resumes = list_resumes(5)
    recent_questions = get_recent_questions(5)
    recent_interviews = list_mock_interviews(5)
    recent_ats_checks = list_ats_checks(5)
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        stats=stats,
        recent_audits=recent_audits,
        recent_resumes=recent_resumes,
        recent_questions=recent_questions,
        recent_interviews=recent_interviews,
        recent_ats_checks=recent_ats_checks,
        now=datetime.now()
    )


@app.route('/dashboard')
def dashboard():
    """Skillverse Main Dashboard view."""
    stats = get_dashboard_stats()
    recent_audits = get_recent_audits(5)
    recent_resumes = list_resumes(5)
    recent_questions = get_recent_questions(5)
    recent_interviews = list_mock_interviews(5)
    recent_ats_checks = list_ats_checks(5)
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        stats=stats,
        recent_audits=recent_audits,
        recent_resumes=recent_resumes,
        recent_questions=recent_questions,
        recent_interviews=recent_interviews,
        recent_ats_checks=recent_ats_checks,
        now=datetime.now()
    )


@app.route('/question-generator', methods=['GET', 'POST'])
def question_generator_page():
    """Active Tool: Interview Question Generator with resume upload & Groq generation."""
    questions = None
    error = None
    if request.method == 'POST':
        questions, error = process_resume_upload(request)

    return render_template(
        'question_generator.html',
        questions=questions,
        error=error,
        active_page='question_generator',
        now=datetime.now()
    )


# ---------------------------------------------------------------------------
# AI Resume Analyzer (Phase 3 Active Tool)
# ---------------------------------------------------------------------------

@app.route('/resume-analyzer', methods=['GET', 'POST'])
def resume_analyzer():
    """Skillverse AI Resume Analyzer: Deep audit, ATS score, skills breakdown & recommendations."""
    analysis = None
    error = None
    filename = None

    if request.method == 'POST':
        if 'resume' not in request.files or request.files['resume'].filename == '':
            error = "Please upload a valid .pdf or .docx resume file."
            return render_template(
                'resume_analyzer.html',
                analysis=None,
                error=error,
                filename=None,
                active_page='resume_analyzer',
                now=datetime.now()
            )

        file = request.files['resume']
        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower()

        if ext not in ['.pdf', '.docx']:
            error = "Unsupported file format. Please upload a PDF (.pdf) or Word document (.docx)."
            return render_template(
                'resume_analyzer.html',
                analysis=None,
                error=error,
                filename=None,
                active_page='resume_analyzer',
                now=datetime.now()
            )

        # Generate a unique temporary filename to prevent file collisions
        temp_name = f"analyze_{uuid.uuid4().hex}_{original_filename}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_name)

        try:
            file.save(temp_filepath)

            # File size sanity check (16 MB cap)
            if os.path.getsize(temp_filepath) > app.config['MAX_CONTENT_LENGTH']:
                error = "File size exceeds the 16MB limit. Please upload a smaller document."
            else:
                # Perform AI resume audit
                analysis, analysis_error = analyze_resume_file(temp_filepath)
                if analysis_error:
                    error = analysis_error
                else:
                    filename = original_filename
                    # Persist audit record to SQLite database
                    try:
                        save_audit(
                            original_filename,
                            analysis.get("overall_score", 70),
                            analysis.get("score_grade", "Competitive"),
                            analysis.get("ats_readiness", {}).get("score", 70),
                            analysis.get("ats_readiness", {}).get("level", "Moderate"),
                            analysis
                        )
                    except Exception:
                        pass

        except Exception as e:
            error = f"An unexpected error occurred while processing your resume: {str(e)}"
        finally:
            # Secure cleanup: Remove uploaded resume immediately after analysis to safeguard candidate privacy
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

    return render_template(
        'resume_analyzer.html',
        analysis=analysis,
        error=error,
        filename=filename,
        active_page='resume_analyzer',
        now=datetime.now()
    )


# ---------------------------------------------------------------------------
# AI Resume Builder Routes & APIs (Phase 4 Active Tool)
# ---------------------------------------------------------------------------

@app.route('/resume-builder')
def resume_builder():
    """Active Tool: Skillverse AI Resume Builder workspace with live A4 preview."""
    return render_template(
        'resume_builder.html',
        active_page='resume_builder',
        now=datetime.now()
    )


@app.route('/api/resume-builder/save', methods=['POST'])
def api_save_resume():
    try:
        payload = request.get_json() or {}
        title = payload.get('title', 'Untitled Resume').strip()
        template = payload.get('template', 'modern')
        data_dict = payload.get('data', {})
        resume_id = payload.get('id')
        if resume_id:
            try:
                resume_id = int(resume_id)
            except ValueError:
                resume_id = None

        saved_id = save_resume(title, template, data_dict, resume_id=resume_id)
        return jsonify({"status": "success", "id": saved_id, "message": "Resume saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/list', methods=['GET'])
def api_list_resumes():
    try:
        resumes = list_resumes(limit=50)
        return jsonify({"status": "success", "resumes": resumes})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/<int:resume_id>', methods=['GET'])
def api_get_resume(resume_id):
    try:
        resume = get_resume(resume_id)
        if not resume:
            return jsonify({"status": "error", "message": "Resume not found."}), 404
        return jsonify({"status": "success", "resume": resume})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/<int:resume_id>', methods=['DELETE'])
def api_delete_resume(resume_id):
    try:
        deleted = delete_resume(resume_id)
        return jsonify({"status": "success", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/generate-summary', methods=['POST'])
def api_generate_summary():
    try:
        payload = request.get_json() or {}
        role = payload.get('role', '')
        years = payload.get('experience_years', '')
        skills = payload.get('skills', '')
        notes = payload.get('raw_notes', '')

        result, error = generate_summary(role, years, skills, notes)
        if error:
            return jsonify({"status": "error", "message": error}), 500
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/improve-bullet', methods=['POST'])
def api_improve_bullet():
    try:
        payload = request.get_json() or {}
        bullet = payload.get('bullet', '')
        role = payload.get('role', '')
        focus = payload.get('focus', 'impact')

        result, error = improve_bullet(bullet, role, focus)
        if error:
            return jsonify({"status": "error", "message": error}), 500
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/suggest-verbs', methods=['GET'])
def api_suggest_verbs():
    try:
        verbs = get_action_verbs()
        return jsonify({"status": "success", "result": verbs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/resume-builder/generate-project-desc', methods=['POST'])
def api_generate_project_desc():
    try:
        payload = request.get_json() or {}
        title = payload.get('title', '')
        tech = payload.get('tech_stack', '')
        highlights = payload.get('highlights', '')

        result, error = generate_project_description(title, tech, highlights)
        if error:
            return jsonify({"status": "error", "message": error}), 500
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# AI Mock Interview Simulator Routes & APIs (Phase 2 Active Tool)
# ---------------------------------------------------------------------------

@app.route('/mock-interview')
def mock_interview():
    """Active Tool: Skillverse AI Mock Interview Simulator with real-time AI scoring."""
    return render_template(
        'mock_interview.html',
        active_page='mock_interview',
        now=datetime.now()
    )


@app.route('/api/mock-interview/start', methods=['POST'])
def api_mock_interview_start():
    try:
        payload = request.get_json() or {}
        role = payload.get('role', 'Full Stack Developer')
        level = payload.get('experience_level', 'Mid-Level (3-5 years)')
        track = payload.get('interview_type', 'Technical')
        count = int(payload.get('count', 5))
        questions = generate_interview_questions(role, level, track, count)
        return jsonify({"status": "success", "questions": questions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/evaluate', methods=['POST'])
def api_mock_interview_evaluate():
    try:
        payload = request.get_json() or {}
        question = payload.get('question', '')
        answer = payload.get('candidate_answer', '')
        role = payload.get('role', 'Professional')
        level = payload.get('experience_level', 'Mid-Level')
        track = payload.get('interview_type', 'Technical')
        evaluation = evaluate_answer(question, answer, role, level, track)
        return jsonify({"status": "success", "evaluation": evaluation})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/complete', methods=['POST'])
def api_mock_interview_complete():
    try:
        payload = request.get_json() or {}
        role = payload.get('role', 'Software Engineer')
        level = payload.get('experience_level', 'Mid-Level')
        track = payload.get('interview_type', 'Technical')
        qa_history = payload.get('qa_history', [])
        report = compile_final_report(role, level, track, qa_history)
        return jsonify({"status": "success", "report": report})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/save', methods=['POST'])
def api_mock_interview_save():
    try:
        payload = request.get_json() or {}
        role = payload.get('role', 'Software Engineer')
        level = payload.get('experience_level', 'Mid-Level')
        track = payload.get('interview_type', 'Technical')
        overall_score = payload.get('overall_score', 0)
        score_grade = payload.get('score_grade', 'Competent')
        summary_feedback = payload.get('summary_feedback', '')
        qa_history = payload.get('qa_history', [])
        saved_id = save_mock_interview(role, level, track, overall_score, score_grade, summary_feedback, qa_history)
        return jsonify({"status": "success", "id": saved_id, "message": "Interview session saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/history', methods=['GET'])
def api_mock_interview_history():
    try:
        interviews = list_mock_interviews(limit=30)
        return jsonify({"status": "success", "interviews": interviews})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/<int:interview_id>', methods=['GET'])
def api_mock_interview_get(interview_id):
    try:
        interview = get_mock_interview(interview_id)
        if not interview:
            return jsonify({"status": "error", "message": "Interview session not found."}), 404
        return jsonify({"status": "success", "interview": interview})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mock-interview/<int:interview_id>', methods=['DELETE'])
def api_mock_interview_delete(interview_id):
    try:
        deleted = delete_mock_interview(interview_id)
        return jsonify({"status": "success", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# ATS Resume Checker Routes & APIs (Phase 3 Active Tool)
# ---------------------------------------------------------------------------

@app.route('/ats-checker')
def ats_checker():
    """Active Tool: Skillverse Dedicated ATS Resume Checker & Parser Simulator."""
    return render_template(
        'ats_checker.html',
        active_page='ats_checker',
        now=datetime.now()
    )


@app.route('/api/ats-checker/scan', methods=['POST'])
def api_ats_checker_scan():
    try:
        if 'resume' not in request.files or request.files['resume'].filename == '':
            return jsonify({"status": "error", "message": "Please upload a valid .pdf or .docx resume file."}), 400

        file = request.files['resume']
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ['.pdf', '.docx']:
            return jsonify({"status": "error", "message": "Unsupported file format. Please upload a PDF (.pdf) or Word document (.docx)."}), 400

        job_description = request.form.get('job_description', '').strip()
        target_role = request.form.get('target_role', '').strip()

        temp_name = f"ats_{uuid.uuid4().hex}_{filename}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_name)
        file.save(temp_filepath)

        try:
            report = audit_resume_for_ats(temp_filepath, job_description=job_description, target_role=target_role)
            report["filename"] = filename
            return jsonify({"status": "success", "report": report})
        finally:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ats-checker/save', methods=['POST'])
def api_ats_checker_save():
    try:
        payload = request.get_json() or {}
        filename = payload.get('filename', 'Resume')
        target_job_title = payload.get('target_job_title', '')
        ats_score = payload.get('ats_score', 0)
        ats_grade = payload.get('ats_grade', 'Moderate')
        format_score = payload.get('format_score', 0)
        keyword_score = payload.get('keyword_score', 0)
        section_score = payload.get('section_score', 0)
        report = payload.get('report', {})

        check_id = save_ats_check(
            filename, target_job_title, ats_score, ats_grade,
            format_score, keyword_score, section_score, report
        )
        return jsonify({"status": "success", "id": check_id, "message": "ATS audit saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ats-checker/history', methods=['GET'])
def api_ats_checker_history():
    try:
        checks = list_ats_checks(limit=30)
        return jsonify({"status": "success", "checks": checks})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ats-checker/<int:check_id>', methods=['GET'])
def api_ats_checker_get(check_id):
    try:
        check = get_ats_check(check_id)
        if not check:
            return jsonify({"status": "error", "message": "ATS audit not found."}), 404
        return jsonify({"status": "success", "check": check})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ats-checker/<int:check_id>', methods=['DELETE'])
def api_ats_checker_delete(check_id):
    try:
        deleted = delete_ats_check(check_id)
        return jsonify({"status": "success", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Coming Soon Feature Routes (Phase 4 Roadmap)
# ---------------------------------------------------------------------------


@app.route('/job-matcher')
def job_matcher():
    return redirect(url_for('dashboard'))


@app.route('/career-roadmap')
def career_roadmap():
    return redirect(url_for('dashboard'))


# ---------------------------------------------------------------------------
# Settings & Preferences (Active Tool)
# ---------------------------------------------------------------------------

@app.route('/settings')
def settings_page():
    """Active Platform Settings & Preferences Control Center."""
    settings = get_all_settings()
    storage = get_storage_stats()

    # Calculate upload cache metrics
    upload_dir = app.config['UPLOAD_FOLDER']
    uploads_count = 0
    uploads_size_bytes = 0
    if os.path.exists(upload_dir):
        files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
        uploads_count = len(files)
        uploads_size_bytes = sum(os.path.getsize(os.path.join(upload_dir, f)) for f in files)
    uploads_size_kb = round(uploads_size_bytes / 1024, 1)

    # Mask API key for secure presentation
    api_key = os.getenv("GROQ_API_KEY", "")
    if api_key and len(api_key) > 8:
        masked_api_key = f"{api_key[:4]}...{api_key[-4:]}"
    elif api_key:
        masked_api_key = "Configured"
    else:
        masked_api_key = "Not Configured"

    return render_template(
        'settings.html',
        settings=settings,
        storage=storage,
        masked_api_key=masked_api_key,
        uploads_count=uploads_count,
        uploads_size_kb=uploads_size_kb,
        active_page='settings',
        now=datetime.now()
    )


@app.route('/api/settings/save', methods=['POST'])
def api_settings_save():
    try:
        payload = request.get_json() or {}
        allowed_keys = {
            "candidate_name", "candidate_email", "candidate_phone", "candidate_location",
            "target_role", "experience_level", "preferred_model", "ai_rigor",
            "evaluation_temperature", "auto_cleanup_uploads", "theme_mode", "font_size"
        }
        for k, v in payload.items():
            if k in allowed_keys:
                set_setting(k, v)
        return jsonify({"status": "success", "message": "Settings saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/settings/test-ai', methods=['POST'])
def api_settings_test_ai():
    try:
        payload = request.get_json() or {}
        model = payload.get('model', 'qwen/qwen3.8-27b')
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return jsonify({"status": "error", "message": "GROQ_API_KEY is not configured in your .env file."}), 400

        groq_client = Groq(api_key=api_key)
        models_to_try = [model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
        # Deduplicate while preserving order
        seen = set()
        candidates = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_error = None
        for m in candidates:
            try:
                start_time = time.time()
                response = groq_client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": "You are Skillverse ping tester. Respond with 'PONG'."},
                        {"role": "user", "content": "PING"}
                    ],
                    max_tokens=10,
                    temperature=0.1
                )
                latency_ms = int(round((time.time() - start_time) * 1000))
                content = response.choices[0].message.content.strip()
                return jsonify({
                    "status": "success",
                    "model": m,
                    "latency_ms": latency_ms,
                    "response": content
                })
            except Exception as ex:
                last_error = ex
                continue

        if last_error:
            raise last_error
        return jsonify({"status": "error", "message": "Unable to connect to Groq AI inference."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/settings/clear-cache', methods=['POST'])
def api_settings_clear_cache():
    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        deleted_count = 0
        bytes_freed = 0
        if os.path.exists(upload_dir):
            for f in os.listdir(upload_dir):
                f_path = os.path.join(upload_dir, f)
                if os.path.isfile(f_path):
                    bytes_freed += os.path.getsize(f_path)
                    try:
                        os.remove(f_path)
                        deleted_count += 1
                    except Exception:
                        pass
        return jsonify({
            "status": "success",
            "files_deleted": deleted_count,
            "bytes_freed_kb": round(bytes_freed / 1024, 1)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/settings/clear-history', methods=['POST'])
def api_settings_clear_history():
    try:
        payload = request.get_json() or {}
        table = payload.get('table', '')
        allowed_tables = {"mock_interviews", "ats_checks", "question_history", "resume_audits"}
        if table not in allowed_tables:
            return jsonify({"status": "error", "message": "Invalid table specified for reset."}), 400

        deleted = clear_table_records(table)
        return jsonify({"status": "success", "table": table, "records_deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/logout')
def logout():
    """Clear session data and redirect safely to the Dashboard."""
    session.clear()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
