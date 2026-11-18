"""
Skillverse AI Resume Analyzer Engine
Powered by Groq Cloud API with structured JSON output and robust fallback.
"""

import os
import json
import logging
from dotenv import load_dotenv
from groq import Groq
from resume_parser import read_resume

# Load environment variables
load_dotenv()

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Prioritized list of compatible Groq chat models
MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b"
]

ANALYSIS_SYSTEM_PROMPT = """You are the Chief Talent Officer and Senior Technical Recruiter for Skillverse, an elite career development platform.
Your task is to analyze candidate resumes with rigor, precision, and constructive guidance.

Output ONLY valid, pure JSON matching this exact structure:
{
  "overall_score": 78,
  "score_grade": "Competitive",
  "score_explanation": "Strong foundational background in modern technologies, but bullet points lack quantifiable impact metrics.",
  "ats_readiness": {
    "score": 75,
    "level": "Moderate",
    "explanation": "Standard section headers and readable layout. However, some technical keywords are buried and date formats vary.",
    "key_findings": [
      "Standard section headings detected",
      "No complex tables or graphics found",
      "Action verbs need strengthening for keyword parsing"
    ]
  },
  "skills_analysis": {
    "technical_skills": ["Python", "Flask", "Docker", "SQL", "Git"],
    "soft_skills": ["Problem Solving", "Team Leadership", "Cross-functional Collaboration"],
    "missing_or_underrepresented": ["CI/CD Pipelines", "Automated Testing (pytest)", "Cloud Architecture (AWS/GCP)"],
    "relevant_keywords": ["Full-stack", "REST APIs", "Microservices", "Scalability"]
  },
  "strengths": [
    "Demonstrated experience building end-to-end full-stack applications",
    "Clear, structured chronological project timeline"
  ],
  "weaknesses": [
    "Most bullet points describe responsibilities rather than business achievements",
    "Missing quantifiable metrics (percentages, dollar amounts, performance gains)"
  ],
  "section_analysis": {
    "summary": {
      "present": true,
      "score": 70,
      "verdict": "Satisfactory",
      "feedback": "Concise summary present, but could better highlight years of experience and target job focus."
    },
    "experience": {
      "present": true,
      "score": 75,
      "verdict": "Needs Improvement",
      "feedback": "Solid work history, but bullet points rely on passive phrases like 'responsible for' instead of impact verbs."
    },
    "education": {
      "present": true,
      "score": 85,
      "verdict": "Strong",
      "feedback": "Degree, major, university, and graduation year clearly listed."
    },
    "skills": {
      "present": true,
      "score": 80,
      "verdict": "Strong",
      "feedback": "Good grouping of technical skills, but could benefit from proficiency tiers."
    },
    "projects": {
      "present": true,
      "score": 75,
      "verdict": "Satisfactory",
      "feedback": "Relevant projects included. Adding live demo links and tech stacks per project would strengthen this."
    },
    "certifications": {
      "present": false,
      "score": 50,
      "verdict": "Missing",
      "feedback": "No formal industry certifications or verified credentials detected."
    }
  },
  "improvement_recommendations": [
    {
      "section": "Work Experience",
      "title": "Adopt the XYZ Impact Formula",
      "action": "Rewrite bullet points using 'Accomplished [X], as measured by [Y], by doing [Z]'.",
      "example_before": "Worked on backend API optimization to make it faster.",
      "example_after": "Optimized backend database queries and caching layers, reducing API response latency by 38% across 100k daily requests."
    },
    {
      "section": "Technical Skills",
      "title": "Highlight Modern DevOps & Testing",
      "action": "Incorporate automated testing tools (e.g. pytest, Jest) and CI/CD tools used in your workflow.",
      "example_before": "Skills: Python, Git",
      "example_after": "Skills: Python, Pytest, GitHub Actions CI/CD, Docker Containerization"
    }
  ]
}

CRITICAL RULES:
1. Do not invent false companies, titles, or fake degrees. Base the critique strictly on the provided resume text.
2. Provide at least 4 detailed improvement recommendations with practical 'before' and 'after' examples.
3. Be fair, constructive, and realistic. Reserve scores above 90 for truly exceptional executive-grade resumes with outstanding metrics.
"""


def get_active_groq_client():
    """Returns an active Groq client or raises an informative error."""
    global client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured in your environment. Please set it in your .env file.")
    if client is None:
        client = Groq(api_key=api_key)
    return client


def analyze_resume_text(resume_text):
    """
    Sends extracted resume text to the Groq LLM and returns parsed structured analysis.
    Returns (analysis_dict, None) on success, or (None, error_message) on failure.
    """
    if not resume_text or len(resume_text.strip()) < 40:
        return None, "The uploaded resume did not contain sufficient readable text. Please ensure it is not a scanned image or blank document."

    # Truncate to maximum 16,000 characters to stay within token context limits comfortably
    truncated_text = resume_text.strip()[:16000]

    groq_client = None
    try:
        groq_client = get_active_groq_client()
    except Exception as e:
        return None, f"Configuration Error: {str(e)}"

    last_error = None
    for model_name in MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Analyze the following resume thoroughly according to your instructions:\n\n---\n{truncated_text}\n---"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2500
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                continue

            analysis_data = json.loads(raw_content)

            # Ensure all required top-level keys exist with defaults
            validated_data = sanitize_analysis_output(analysis_data)
            return validated_data, None

        except json.JSONDecodeError as jde:
            last_error = f"Failed to parse AI response into structured data ({jde})."
            continue
        except Exception as err:
            last_error = f"{model_name}: {str(err)}"
            continue

    return None, f"AI Analysis Service temporarily unavailable: {last_error}"


def sanitize_analysis_output(data):
    """Guarantees default fallback values for any missing keys in the LLM response."""
    if not isinstance(data, dict):
        data = {}

    data.setdefault("overall_score", 70)
    data.setdefault("score_grade", "Competitive")
    data.setdefault("score_explanation", "Resume has been audited. See detailed sections below for improvement points.")

    # ATS readiness defaults
    ats = data.setdefault("ats_readiness", {})
    if not isinstance(ats, dict):
        ats = {}
        data["ats_readiness"] = ats
    ats.setdefault("score", 70)
    ats.setdefault("level", "Moderate")
    ats.setdefault("explanation", "Standard formatting detected. Review key findings to optimize parseability.")
    ats.setdefault("key_findings", ["Standard text detected", "Check keyword density against target roles"])

    # Skills analysis defaults
    skills = data.setdefault("skills_analysis", {})
    if not isinstance(skills, dict):
        skills = {}
        data["skills_analysis"] = skills
    skills.setdefault("technical_skills", [])
    skills.setdefault("soft_skills", [])
    skills.setdefault("missing_or_underrepresented", [])
    skills.setdefault("relevant_keywords", [])

    data.setdefault("strengths", ["Clear educational or professional background", "Structured presentation"])
    data.setdefault("weaknesses", ["Could add more quantifiable metrics and results"])

    # Section analysis defaults
    sections = data.setdefault("section_analysis", {})
    if not isinstance(sections, dict):
        sections = {}
        data["section_analysis"] = sections

    default_sections = ["summary", "experience", "education", "skills", "projects", "certifications"]
    for sec in default_sections:
        s = sections.setdefault(sec, {})
        if not isinstance(s, dict):
            s = {}
            sections[sec] = s
        s.setdefault("present", True)
        s.setdefault("score", 70)
        s.setdefault("verdict", "Satisfactory")
        s.setdefault("feedback", f"Section evaluated for clarity and impact.")

    # Recommendations
    recs = data.setdefault("improvement_recommendations", [])
    if not isinstance(recs, list) or len(recs) == 0:
        data["improvement_recommendations"] = [
            {
                "section": "Work Experience",
                "title": "Quantify Achievements",
                "action": "Add specific numbers, percentages, or scale metrics to your bullet points to demonstrate concrete results.",
                "example_before": "Responsible for managing project deliverables and code reviews.",
                "example_after": "Delivered 12 sprint milestones ahead of schedule, improving team code review turnaround by 25%."
            }
        ]

    return data


def analyze_resume_file(file_path):
    """
    High-level entry point: reads resume file, extracts text, and performs analysis.
    Returns (analysis_data, error_message).
    """
    try:
        text = read_resume(file_path)
    except Exception as e:
        return None, f"File Parsing Error: {str(e)}"

    return analyze_resume_text(text)
