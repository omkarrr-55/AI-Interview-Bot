from datetime import datetime
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from resume_parser import extract_keywords
from question_generator import generate_questions
from resume_analyzer import analyze_resume_file

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

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
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        now=datetime.now()
    )


@app.route('/dashboard')
def dashboard():
    """Skillverse Main Dashboard view."""
    return render_template(
        'dashboard.html',
        active_page='dashboard',
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
# Coming Soon Feature Routes (Phase 4 Roadmap)
# ---------------------------------------------------------------------------


@app.route('/resume-builder')
def resume_builder():
    return render_template(
        'coming_soon.html',
        feature_title='AI Resume Builder',
        feature_icon='bi-file-earmark-text',
        feature_description='Create professional, ATS-optimized resumes in minutes with guided AI bullet point generation and modern templates.',
        planned_items=[
            'ATS-proof professional layout templates',
            'Role-targeted bullet point generation with one-click adoption',
            'Real-time keyword density and score checker',
            'One-click PDF and DOCX export'
        ],
        active_page='resume_builder',
        now=datetime.now()
    )


@app.route('/mock-interview')
def mock_interview():
    return render_template(
        'coming_soon.html',
        feature_title='Mock Interview Simulator',
        feature_icon='bi-mic-fill',
        feature_description='Engage in realistic conversational technical and behavioral mock interviews with turn-based voice or text interaction.',
        planned_items=[
            'Speech-to-text voice recognition for verbal practice',
            'Automated STAR behavioral response framework scoring',
            'Adaptive follow-up questions tailored to your answers',
            'Post-interview performance scorecards with model answers'
        ],
        active_page='mock_interview',
        now=datetime.now()
    )


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
