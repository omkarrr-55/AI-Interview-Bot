from datetime import datetime
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
from resume_parser import extract_keywords
from question_generator import generate_questions

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

@app.route('/', methods=['GET', 'POST'])
def index():
    questions = None
    error = None
    if request.method == 'POST':
        if 'resume' not in request.files or request.files['resume'].filename == '':
            error = "Please upload a valid .pdf or .docx resume file."
        else:
            file = request.files['resume']
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(filepath)
                # Extract keywords from resume
                keywords = extract_keywords(filepath)
                # Generate questions using Groq
                questions = generate_questions(keywords)
                if not questions:
                    error = "Could not generate questions. Please ensure your Groq API key is set and the resume has readable text."
            except Exception as e:
                error = f"Error processing resume: {str(e)}"

    return render_template('index.html', questions=questions, error=error, now=datetime.now())

if __name__ == '__main__':
    app.run(debug=True)
