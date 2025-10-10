# app.py
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import os
from resume_parser import extract_keywords
from question_generator import generate_questions

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    questions = None
    if request.method == 'POST':
        if 'resume' in request.files:
            file = request.files['resume']
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            keywords = extract_keywords(filepath)
            questions = generate_questions(keywords)

    return render_template('index.html', questions=questions)

if __name__ == '__main__':
    app.run(debug=True)
