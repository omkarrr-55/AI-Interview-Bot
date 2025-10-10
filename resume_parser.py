# resume_parser.py
import docx
import re
from nltk.corpus import stopwords

def read_resume(file_path):
    doc = docx.Document(file_path)
    full_text = " ".join([para.text for para in doc.paragraphs])
    return full_text

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)  # remove special characters
    words = text.split()
    stop_words = set(stopwords.words('english'))
    keywords = [word for word in words if word not in stop_words]
    return list(set(keywords))  # remove duplicates

def extract_keywords(file_path):
    text = read_resume(file_path)
    keywords = clean_text(text)
    return keywords
