"""
ats_checker.py - Skillverse Dedicated ATS Resume Checker Engine
Provides structural layout inspection (tables, columns, graphics, headers/footers),
standard section taxonomy auditing, target job keyword matching, explainable scoring,
and simulated plain-text ATS parsing.
"""

import os
import re
import json
from dotenv import load_dotenv
from groq import Groq
import PyPDF2
from docx import Document
from resume_parser import clean_text

# Load environment configuration
load_dotenv()
_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=_api_key) if _api_key else None

MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b"
]

# Standard ATS Section Taxonomy
STANDARD_SECTION_PATTERNS = {
    "contact": {
        "title": "Contact & Personal Information",
        "patterns": [r"\bemail\b", r"\bphone\b", r"\bmobile\b", r"\blinkedin\b", r"\bgithub\b", r"\blocation\b", r"\baddress\b"],
        "essential": True
    },
    "summary": {
        "title": "Professional Summary / Objective",
        "patterns": [r"\bprofessional summary\b", r"\bsummary\b", r"\bexecutive summary\b", r"\bprofile\b", r"\bobjective\b", r"\bcareer objective\b"],
        "essential": False
    },
    "experience": {
        "title": "Work Experience / Employment History",
        "patterns": [r"\bwork experience\b", r"\bprofessional experience\b", r"\bemployment history\b", r"\bexperience\b", r"\bcareer history\b"],
        "essential": True
    },
    "education": {
        "title": "Education & Academic Credentials",
        "patterns": [r"\beducation\b", r"\bacademic background\b", r"\bacademics\b", r"\bdegrees\b", r"\buniversity\b", r"\bcollege\b"],
        "essential": True
    },
    "skills": {
        "title": "Technical & Core Skills",
        "patterns": [r"\btechnical skills\b", r"\bskills\b", r"\bcore competencies\b", r"\bkey skills\b", r"\btechnologies\b", r"\bexpertise\b"],
        "essential": True
    },
    "projects": {
        "title": "Projects & Portfolio",
        "patterns": [r"\bprojects\b", r"\bpersonal projects\b", r"\bkey projects\b", r"\bportfolio\b"],
        "essential": False
    },
    "certifications": {
        "title": "Certifications & Credentials",
        "patterns": [r"\bcertifications\b", r"\bcertificates\b", r"\blicenses\b", r"\bcredentials\b"],
        "essential": False
    }
}

# Unconventional / Risky Section Titles that confuse ATS parsers
RISKY_HEADING_PATTERNS = [
    (r"\bwhere i've been\b", "Work Experience"),
    (r"\bmy journey\b", "Professional Experience"),
    (r"\bwhat i do\b", "Summary or Skills"),
    (r"\barsenal\b", "Skills / Technologies"),
    (r"\btools of the trade\b", "Technical Skills"),
    (r"\bhustles\b", "Projects or Experience"),
    (r"\bgigs\b", "Experience"),
    (r"\bbrain dump\b", "Skills"),
    (r"\blife achievements\b", "Awards or Experience")
]

# Common High-Demand Industry Tech Skills for Baseline Keyword Audits
BASELINE_KEYWORDS = [
    "python", "javascript", "typescript", "react", "node.js", "flask", "django",
    "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes", "aws", "gcp",
    "azure", "ci/cd", "git", "rest apis", "microservices", "unit testing", "agile",
    "linux", "html", "css", "data structures", "system design"
]


# ---------------------------------------------------------------------------
# 1. Structural & File Hygiene Inspector
# ---------------------------------------------------------------------------

def inspect_docx_structure(file_path: str) -> dict:
    """Performs deep binary layout inspection on a .docx document."""
    doc = Document(file_path)

    # 1. Inspect Tables
    table_count = len(doc.tables)
    total_cells = sum(len(row.cells) for table in doc.tables for row in table.rows)
    has_nested_tables = False
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if len(cell.tables) > 0:
                    has_nested_tables = True

    # 2. Inspect Headers & Footers
    header_text = ""
    footer_text = ""
    for section in doc.sections:
        for p in section.header.paragraphs:
            header_text += " " + p.text
        for p in section.footer.paragraphs:
            footer_text += " " + p.text

    # Check if contact information is trapped in header/footer
    email_in_header = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', header_text + footer_text))
    phone_in_header = bool(re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', header_text + footer_text))

    # 3. Extract body text
    body_paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(body_paragraphs)
    word_count = len(full_text.split())

    return {
        "file_type": "docx",
        "table_count": table_count,
        "total_table_cells": total_cells,
        "has_nested_tables": has_nested_tables,
        "header_contact_risk": email_in_header or phone_in_header,
        "word_count": word_count,
        "char_count": len(full_text),
        "is_scanned_image": False,
        "extracted_text": full_text
    }


def inspect_pdf_structure(file_path: str) -> dict:
    """Performs deep structural layout inspection on a .pdf document."""
    full_text = ""
    page_count = 0
    image_count = 0

    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        page_count = len(reader.pages)

        for page in reader.pages:
            t = page.extract_text() or ""
            full_text += t + "\n"

            # Check embedded images / XObjects
            try:
                resources = page.get('/Resources')
                if resources:
                    xObject = resources.get('/XObject')
                    if xObject:
                        for obj in xObject:
                            if xObject[obj].get('/Subtype') == '/Image':
                                image_count += 1
            except Exception:
                pass

    total_chars = len(full_text.strip())
    word_count = len(full_text.split())

    # Detect scanned document: Very few characters relative to page count or file size
    file_size_kb = os.path.getsize(file_path) / 1024.0
    is_scanned_image = False
    if total_chars < 80 and file_size_kb > 40:
        is_scanned_image = True

    return {
        "file_type": "pdf",
        "page_count": page_count,
        "table_count": 0,  # PDFs flatten tables into text streams
        "image_count": image_count,
        "is_scanned_image": is_scanned_image,
        "word_count": word_count,
        "char_count": total_chars,
        "header_contact_risk": False,
        "extracted_text": full_text.strip()
    }


def inspect_document(file_path: str) -> dict:
    """Dispatches document inspection based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return inspect_docx_structure(file_path)
    elif ext == ".pdf":
        return inspect_pdf_structure(file_path)
    else:
        raise ValueError("Unsupported format. Please upload a .pdf or .docx file.")


# ---------------------------------------------------------------------------
# 2. Section Taxonomy & Headings Verifier
# ---------------------------------------------------------------------------

def audit_sections_and_headings(text: str) -> dict:
    """
    Audits document text against standard enterprise ATS section taxonomy
    and detects non-standard or missing sections.
    """
    lower_text = text.lower()
    detected_sections = {}
    missing_sections = []

    # Check standard sections
    for sec_key, sec_meta in STANDARD_SECTION_PATTERNS.items():
        found = False
        for pat in sec_meta["patterns"]:
            if re.search(pat, lower_text):
                found = True
                break
        detected_sections[sec_key] = {
            "title": sec_meta["title"],
            "present": found,
            "essential": sec_meta["essential"]
        }
        if not found and sec_meta["essential"]:
            missing_sections.append(sec_meta["title"])

    # Detect risky / non-standard headings
    unconventional_findings = []
    for risky_pat, standard_equiv in RISKY_HEADING_PATTERNS:
        if re.search(risky_pat, lower_text):
            unconventional_findings.append({
                "detected": risky_pat.strip(r"\b"),
                "recommended": standard_equiv
            })

    # Contact Info check (Email & Phone presence)
    has_email = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text))
    has_phone = bool(re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text))
    has_linkedin = "linkedin.com" in lower_text

    return {
        "sections": detected_sections,
        "missing_essential_sections": missing_sections,
        "unconventional_headings": unconventional_findings,
        "contact_info": {
            "has_email": has_email,
            "has_phone": has_phone,
            "has_linkedin": has_linkedin
        }
    }


# ---------------------------------------------------------------------------
# 3. Target Job Keyword Extraction & Matching
# ---------------------------------------------------------------------------

def extract_keywords_from_job(job_description: str) -> list:
    """
    Extracts high-impact technical skills and qualifications from a job description
    using Groq LLM with fallback heuristics.
    """
    if not job_description or len(job_description.strip()) < 30:
        return BASELINE_KEYWORDS

    system_prompt = (
        "You are an automated Applicant Tracking System (ATS) keyword parser. "
        "Extract the top 15 most important technical skills, tools, frameworks, and job-critical keywords from the provided job description. "
        "Output ONLY a pure JSON array of lowercase strings: [\"keyword1\", \"keyword2\", ...]. No explanations or fences."
    )
    user_prompt = f"Job Description:\n{job_description[:3000]}\n\nExtract the critical ATS search keywords."

    if client:
        for model_name in MODELS:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.2
                )
                raw = resp.choices[0].message.content.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                parsed = json.loads(raw)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return [str(k).strip().lower() for k in parsed if len(str(k)) > 1]
            except Exception:
                continue

    # Fallback heuristic: token cleaning & common tech terms
    tokens = clean_text(job_description)
    matched_baseline = [k for k in BASELINE_KEYWORDS if k in job_description.lower()]
    combined = list(set(matched_baseline + [t for t in tokens if len(t) > 3][:12]))
    return combined[:15] if combined else BASELINE_KEYWORDS[:12]


def match_keywords_against_resume(resume_text: str, target_keywords: list) -> dict:
    """
    Cross-references target keywords against resume text, calculating frequency,
    matched keywords, missing keywords, and keyword stuffing warnings.
    """
    lower_resume = resume_text.lower()
    matched = []
    missing = []
    stuffed_keywords = []

    for kw in target_keywords:
        kw_clean = kw.strip().lower()
        # Word boundary or exact substring search
        pattern = r'\b' + re.escape(kw_clean) + r'\b'
        occurrences = len(re.findall(pattern, lower_resume))

        if occurrences > 0:
            matched.append({"keyword": kw_clean, "count": occurrences})
            if occurrences >= 9:
                stuffed_keywords.append({"keyword": kw_clean, "count": occurrences})
        else:
            missing.append(kw_clean)

    total = len(target_keywords)
    match_rate = round((len(matched) / total * 100)) if total > 0 else 75

    return {
        "matched": matched,
        "missing": missing,
        "match_rate": match_rate,
        "stuffed_keywords": stuffed_keywords,
        "total_target_keywords": total
    }


# ---------------------------------------------------------------------------
# 4. Explainable Scoring Engine
# ---------------------------------------------------------------------------

def calculate_ats_score(structure_info: dict, section_info: dict, keyword_info: dict) -> dict:
    """
    Calculates an explainable 0-100 ATS Compatibility Score based on:
    - Parseability & File Hygiene (40%)
    - Job Description / Keyword Relevance (35%)
    - Standard Section Taxonomy (25%)
    """
    # 1. Format & Parseability Score (Base 100)
    format_deductions = 0
    issues_critical = []
    issues_warning = []
    issues_passed = []

    if structure_info["is_scanned_image"]:
        format_deductions += 60
        issues_critical.append("Document appears to be a scanned image or lacks selectable text. Automated ATS parsers cannot read image-only PDFs without OCR.")
    else:
        issues_passed.append("Selectable plain-text stream verified; character density is clean and readable.")

    if structure_info.get("table_count", 0) > 0:
        tbl_cnt = structure_info["table_count"]
        if tbl_cnt > 2 or structure_info.get("has_nested_tables"):
            format_deductions += 20
            issues_critical.append(f"Detected {tbl_cnt} complex or nested tables. Many enterprise ATS systems (Workday, Taleo) read across table cells rather than down columns, corrupting reading order.")
        else:
            format_deductions += 8
            issues_warning.append(f"Detected {tbl_cnt} table element(s). Keep table formatting minimal or convert to simple bulleted lists.")
    else:
        issues_passed.append("No complex tables detected. Document avoids column-interleaving parsing scrambles.")

    if structure_info.get("header_contact_risk"):
        format_deductions += 15
        issues_critical.append("Contact information (email or phone) was detected inside the document header/footer. Legacy ATS parsers frequently strip headers, which will drop your contact info.")
    else:
        issues_passed.append("Contact details are positioned in the main document body.")

    if structure_info.get("image_count", 0) > 3:
        format_deductions += 10
        issues_warning.append(f"Detected {structure_info['image_count']} embedded image/graphic objects. Keep graphics minimal as graphic layers can disrupt text extraction flow.")
    elif structure_info.get("image_count", 0) == 0:
        issues_passed.append("Zero embedded image objects; clean text-first layout.")

    format_score = max(15, min(100, 100 - format_deductions))

    # 2. Keyword Match Score (35%)
    keyword_score = keyword_info["match_rate"]
    if len(keyword_info["missing"]) > 0:
        issues_warning.append(f"Missing {len(keyword_info['missing'])} target job keywords (e.g. {', '.join(keyword_info['missing'][:3])}). ATS recruiter search algorithms rank high-frequency matches higher.")
    else:
        issues_passed.append("Strong keyword coverage against target requirements.")

    if len(keyword_info.get("stuffed_keywords", [])) > 0:
        stuffed = [k["keyword"] for k in keyword_info["stuffed_keywords"]]
        issues_warning.append(f"Potential keyword stuffing detected for: {', '.join(stuffed)}. Mentioning terms more than 8 times can trigger ATS spam filters.")

    # 3. Section Completeness Score (25%)
    section_deductions = 0
    missing_ess = section_info["missing_essential_sections"]
    if missing_ess:
        for m in missing_ess:
            section_deductions += 20
            issues_critical.append(f"Missing essential ATS section: '{m}'. Recruiters filter candidate pools by required standard sections.")
    else:
        issues_passed.append("All core ATS sections detected (Contact, Work Experience, Education, Skills).")

    # Contact check
    ci = section_info["contact_info"]
    if not ci["has_email"]:
        section_deductions += 20
        issues_critical.append("No valid email address detected in the document body.")
    if not ci["has_phone"]:
        section_deductions += 10
        issues_warning.append("No phone number detected in the document body.")

    # Unconventional headings
    if section_info["unconventional_headings"]:
        for uh in section_info["unconventional_headings"]:
            section_deductions += 8
            issues_warning.append(f"Unconventional section heading detected ('{uh['detected']}'). ATS parsers map sections to standard terms like '{uh['recommended']}'.")

    section_score = max(20, min(100, 100 - section_deductions))

    # Holistic Weighted ATS Score
    overall_ats_score = round((0.40 * format_score) + (0.35 * keyword_score) + (0.25 * section_score))
    overall_ats_score = max(20, min(98, overall_ats_score))

    if overall_ats_score >= 85:
        ats_grade = "High ATS Parseability"
        status_label = "Pass"
    elif overall_ats_score >= 70:
        ats_grade = "Moderate ATS Parseability"
        status_label = "Warning"
    else:
        ats_grade = "Low ATS Parseability"
        status_label = "Critical Risk"

    return {
        "overall_score": overall_ats_score,
        "ats_grade": ats_grade,
        "status_label": status_label,
        "dimension_scores": {
            "format_parseability": format_score,
            "keyword_match": keyword_score,
            "section_structure": section_score
        },
        "issues_critical": issues_critical,
        "issues_warning": issues_warning,
        "issues_passed": issues_passed
    }


# ---------------------------------------------------------------------------
# 5. Main ATS Audit Controller
# ---------------------------------------------------------------------------

def audit_resume_for_ats(file_path: str, job_description: str = "", target_role: str = "") -> dict:
    """
    Orchestrates end-to-end ATS parsing audit:
    - Structure inspection
    - Section taxonomy check
    - Keyword matching
    - Mathematical scoring
    - Actionable fix checklist
    """
    # 1. Structural file audit
    structure_info = inspect_document(file_path)
    resume_text = structure_info["extracted_text"]

    # 2. Section taxonomy check
    section_info = audit_sections_and_headings(resume_text)

    # 3. Target job keyword extraction & match
    target_keywords = extract_keywords_from_job(job_description)
    keyword_info = match_keywords_against_resume(resume_text, target_keywords)

    # 4. Score calculation
    score_data = calculate_ats_score(structure_info, section_info, keyword_info)

    # 5. Construct actionable fix checklist
    checklist = []
    for issue in score_data["issues_critical"]:
        checklist.append({"priority": "High (Fix Immediately)", "action": issue, "type": "critical"})
    for issue in score_data["issues_warning"]:
        checklist.append({"priority": "Medium (Recommended)", "action": issue, "type": "warning"})

    if not checklist:
        checklist.append({
            "priority": "Maintenance",
            "action": "Your resume satisfies all primary ATS parseability benchmarks. Keep formatting clean and tailor keywords per application.",
            "type": "pass"
        })

    return {
        "filename": os.path.basename(file_path),
        "target_role": target_role or "General Tech Opportunity",
        "has_job_description": bool(job_description.strip()),
        "overall_score": score_data["overall_score"],
        "ats_grade": score_data["ats_grade"],
        "status_label": score_data["status_label"],
        "dimension_scores": score_data["dimension_scores"],
        "issues_critical": score_data["issues_critical"],
        "issues_warning": score_data["issues_warning"],
        "issues_passed": score_data["issues_passed"],
        "checklist": checklist,
        "keyword_audit": {
            "match_rate": keyword_info["match_rate"],
            "matched_keywords": keyword_info["matched"],
            "missing_keywords": keyword_info["missing"],
            "total_target_keywords": keyword_info["total_target_keywords"]
        },
        "section_audit": section_info["sections"],
        "structure_summary": {
            "word_count": structure_info["word_count"],
            "char_count": structure_info["char_count"],
            "table_count": structure_info.get("table_count", 0),
            "image_count": structure_info.get("image_count", 0),
            "is_scanned": structure_info["is_scanned_image"]
        },
        "simulated_ats_text_preview": resume_text[:1800]
    }
