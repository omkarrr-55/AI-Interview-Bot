# resume_parser.py
import os
import re
import nltk
from docx import Document
import PyPDF2

# Ensure NLTK stopwords are available with a graceful, offline-friendly fallback
DEFAULT_STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
    'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom',
    'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an',
    'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at',
    'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on',
    'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
    'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
    'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now'
}

try:
    from nltk.corpus import stopwords
    stop_words = set(stopwords.words('english'))
except Exception:
    stop_words = DEFAULT_STOPWORDS


def read_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
    return text


def read_docx(file_path):
    doc = Document(file_path)
    return " ".join([para.text for para in doc.paragraphs])


def read_resume(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return read_docx(file_path)
    elif ext == ".pdf":
        return read_pdf(file_path)
    else:
        raise ValueError("Unsupported file format. Please upload a .docx or .pdf resume.")


def clean_text(text):
    text = text.lower()
    # Preserve technical symbols like c++, c#, .net, node.js, ci/cd
    text = re.sub(r'[^a-zA-Z0-9\s\+\#\.\-]', ' ', text)
    words = text.split()
    cleaned_words = []
    for word in words:
        w = word.strip(".-")
        if w and w not in stop_words and len(w) > 1:
            cleaned_words.append(w)
    return list(set(cleaned_words))  # remove duplicates


def extract_keywords(file_path):
    text = read_resume(file_path)
    keywords = clean_text(text)
    return keywords
