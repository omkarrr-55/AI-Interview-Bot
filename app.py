from datetime import datetime
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from resume_parser import extract_keywords
from question_generator import generate_questions
from resume_analyzer import analyze_resume_file
from db import (
    init_db, save_resume, get_resume, list_resumes, delete_resume,
    save_audit, get_recent_audits,
    save_question_history, get_recent_questions,
    save_mock_interview, get_mock_interview, list_mock_interviews, delete_mock_interview,
    get_dashboard_stats
)
from resume_builder import (
    generate_summary, improve_bullet, generate_project_description, get_action_verbs
)
from interview_simulator import (
    generate_interview_questions, evaluate_answer, compile_final_report
)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
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
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        stats=stats,
        recent_audits=recent_audits,
        recent_resumes=recent_resumes,
        recent_questions=recent_questions,
        recent_interviews=recent_interviews,
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
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        stats=stats,
        recent_audits=recent_audits,
        recent_resumes=recent_resumes,
        recent_questions=recent_questions,
        recent_interviews=recent_interviews,
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
# Coming Soon Feature Routes (Phase 4 Roadmap)
# ---------------------------------------------------------------------------


@app.route('/ats-checker')
def ats_checker():
    return render_template(
        'coming_soon.html',
        feature_title='ATS Resume Checker',
        feature_icon='bi-shield-check',
        feature_description='Simulate enterprise Applicant Tracking System parsers (Workday, Greenhouse, Lever) to ensure 100% parseability.',
        planned_items=[
            'Parseability test for columns, tables, headers, and fonts',
            'ATS compatibility score calculated on a 0-100 scale',
            'Common parsing pitfall detection and automatic fix suggestions',
            'Recruiter search keyword visibility audit'
        ],
        active_page='ats_checker',
        now=datetime.now()
    )


@app.route('/job-matcher')
def job_matcher():
    return render_template(
        'coming_soon.html',
        feature_title='Job Description Matcher',
        feature_icon='bi-bullseye',
        feature_description='Compare your resume directly against real job descriptions to identify skill gaps and fine-tune your application before submitting.',
        planned_items=[
            'Direct side-by-side job description comparison',
            'Missing hard skill and qualification gap detector',
            'Semantic match percentage score',
            'Custom tailored resume bullet suggestions'
        ],
        active_page='job_matcher',
        now=datetime.now()
    )


@app.route('/career-roadmap')
def career_roadmap():
    return render_template(
        'coming_soon.html',
        feature_title='Career Roadmap & Pathways',
        feature_icon='bi-signpost-split-fill',
        feature_description='Personalized milestone-driven growth pathways designed to guide your progression from your current role to your dream career.',
        planned_items=[
            'Role progression milestones (Junior to Staff Engineer / Manager)',
            'Recommended certifications, books, and courses for identified gaps',
            'Portfolio project recommendations based on trending tech stacks',
            'Market salary benchmarks and demand analysis'
        ],
        active_page='career_roadmap',
        now=datetime.now()
    )


@app.route('/settings')
def settings_page():
    return render_template(
        'coming_soon.html',
        feature_title='Settings & Preferences',
        feature_icon='bi-gear-fill',
        feature_description='Configure your profile, preferred AI models, target job roles, and platform notification preferences.',
        planned_items=[
            'Target career title and experience level configuration',
            'Groq model parameters & temperature customization',
            'Local resume storage management and deletion controls',
            'Dark / Light theme preferences'
        ],
        active_page='settings',
        now=datetime.now()
    )


if __name__ == '__main__':
    app.run(debug=True)
