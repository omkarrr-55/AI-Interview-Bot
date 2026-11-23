"""
Skillverse AI Resume Builder Engine
Powered by Groq Cloud API with prioritized model fallback and anti-hallucination guardrails.
"""

import os
import json
import logging
from dotenv import load_dotenv
from groq import Groq

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


def _call_groq(prompt, system_prompt, json_mode=False, max_tokens=1000):
    """Executes a prompt across the prioritized Groq model cascade with graceful fallback."""
    if not GROQ_API_KEY or not client:
        return None, "Groq API key is not configured. Please set GROQ_API_KEY in your .env file."

    last_error = None
    for model_name in MODELS:
        try:
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": max_tokens
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip(), None
        except Exception as e:
            last_error = str(e)
            continue

    return None, f"AI generation service temporarily unavailable: {last_error}"


# ---------------------------------------------------------------------------
# AI Feature: Professional Summary Generator
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """You are an elite Executive Career Coach and Resume Strategist at Skillverse.
Your objective is to craft high-impact, professional resume summaries based ONLY on the user's provided details.

CRITICAL RULES:
1. Never invent or assume companies, degrees, unmentioned skills, or unverifiable awards.
2. Produce 3 distinct tonal options:
   - "impact": Focus on quantifiable results and business value.
   - "technical": Focus on technical stack proficiency, architecture, and craftsmanship.
   - "concise": A punchy 2-sentence summary ideal for compact 1-page resumes.
3. Output MUST be valid, pure JSON matching this exact structure:
{
  "impact": "Results-oriented Software Engineer with 4+ years of experience building scalable backend APIs...",
  "technical": "Full-stack Developer specialized in Python, Flask, and React...",
  "concise": "Experienced Software Engineer with a proven track record of shipping cloud-native applications."
}
"""

def generate_summary(role, experience_years, skills, raw_notes=""):
    """Generates three tailored resume summary options using candidate details."""
    prompt = (
        f"Target Role / Title: {role or 'Software Professional'}\n"
        f"Years of Experience: {experience_years or '1-3 years'}\n"
        f"Core Skills: {skills or 'Modern software development'}\n"
        f"Additional Background / Notes: {raw_notes or 'None'}\n\n"
        "Generate 3 professional summary variations adhering strictly to the JSON schema."
    )

    raw_json, error = _call_groq(prompt, SUMMARY_SYSTEM_PROMPT, json_mode=True, max_tokens=1200)
    if error:
        # Fallback offline-generated template summary
        return {
            "impact": f"Results-driven {role or 'Professional'} with {experience_years or 'relevant'} experience in {skills or 'key technologies'}, dedicated to engineering robust solutions and measurable business impact.",
            "technical": f"{role or 'Specialist'} with deep hands-on expertise across {skills or 'modern stacks'}, focused on high-performance development and clean architecture.",
            "concise": f"Adaptable {role or 'Professional'} passionate about building scalable solutions and delivering high-quality deliverables in fast-paced environments."
        }, None

    try:
        data = json.loads(raw_json)
        return data, None
    except Exception:
        return {
            "impact": raw_json,
            "technical": raw_json,
            "concise": raw_json
        }, None


# ---------------------------------------------------------------------------
# AI Feature: Bullet Point Optimizer & Action Verbs
# ---------------------------------------------------------------------------

BULLET_SYSTEM_PROMPT = """You are a Principal Technical Recruiter and Resume Optimizer.
Your job is to transform candidate draft bullet points into compelling, ATS-optimized accomplishment statements using the Google XYZ framework ("Accomplished [X] as measured by [Y], by doing [Z]").

CRITICAL RULES:
1. Never invent fictional companies or unmentioned tools.
2. Start with a powerful, dynamic past-tense action verb (e.g., Architected, Engineered, Spearheaded, Optimized, Streamlined).
3. If the user provided numbers, incorporate them cleanly. If not, include intuitive bracketed metric placeholders like "[reduced latency by X%]" or "[supporting X daily users]".
4. Output MUST be valid, pure JSON matching this exact structure:
{
  "improved_bullet": "Spearheaded the migration of legacy microservices to containerized Docker containers, decreasing deployment cycle time by [35%] and eliminating server drift.",
  "action_verb_used": "Spearheaded",
  "key_improvements": "Replaced passive phrasing with strong leadership action verb, highlighted technical scale, and framed outcome using quantifiable metrics.",
  "alternative_bullet": "Engineered containerized microservices deployment pipeline using Docker, improving developer delivery cadence and infrastructure reliability."
}
"""

def improve_bullet(bullet_text, role=None, focus="impact"):
    """Enhances a resume bullet point with strong action verbs and quantified impact."""
    if not bullet_text or not bullet_text.strip():
        return None, "Please provide a bullet point draft to optimize."

    prompt = (
        f"Candidate Target Role: {role or 'Professional'}\n"
        f"Optimization Focus: {focus}\n"
        f"Original Draft Bullet: \"{bullet_text.strip()}\"\n\n"
        "Transform this into an elite resume bullet statement."
    )

    raw_json, error = _call_groq(prompt, BULLET_SYSTEM_PROMPT, json_mode=True, max_tokens=800)
    if error:
        # Graceful fallback heuristic
        cleaned = bullet_text.strip().lstrip("-*• ")
        return {
            "improved_bullet": f"Spearheaded {cleaned.lower() if cleaned else 'key initiative'}, optimizing overall project deliverables and team productivity by [X%].",
            "action_verb_used": "Spearheaded",
            "key_improvements": "Strengthened action verb and added outcome measurement placeholder.",
            "alternative_bullet": f"Engineered solutions for {cleaned.lower() if cleaned else 'operational workflow'}, enhancing system efficiency and stakeholder satisfaction."
        }, None

    try:
        data = json.loads(raw_json)
        return data, None
    except Exception:
        return {
            "improved_bullet": raw_json,
            "action_verb_used": "Optimized",
            "key_improvements": "Rephrased for professional clarity.",
            "alternative_bullet": raw_json
        }, None


# ---------------------------------------------------------------------------
# AI Feature: Project Description Generator
# ---------------------------------------------------------------------------

PROJECT_SYSTEM_PROMPT = """You are a Technical Talent Director.
Create 2-3 concise, high-impact resume bullet points for a candidate's portfolio project based strictly on their provided project name, technologies, and features.

Output MUST be valid, pure JSON matching:
{
  "bullets": [
    "Architected full-stack web application utilizing Flask and SQLite, serving over [X] concurrent requests with sub-200ms response times.",
    "Engineered responsive front-end interface with modern CSS and Jinja2 templates, ensuring complete mobile and desktop cross-browser compatibility.",
    "Integrated Groq Cloud LLM APIs with multi-model fallback cascade, reducing API downtime by [40%]."
  ]
}
"""

def generate_project_description(title, tech_stack, highlights=""):
    """Generates structured project bullet points for technical and professional resumes."""
    prompt = (
        f"Project Title: {title or 'Software Project'}\n"
        f"Tech Stack / Tools: {tech_stack or 'Python, Web Technologies'}\n"
        f"Key Features & Scope: {highlights or 'Full-stack application with automated workflows'}\n\n"
        "Generate 2 to 3 punchy resume bullets."
    )

    raw_json, error = _call_groq(prompt, PROJECT_SYSTEM_PROMPT, json_mode=True, max_tokens=800)
    if error:
        return {
            "bullets": [
                f"Developed {title or 'full-stack solution'} using {tech_stack or 'modern technologies'}, implementing core features and responsive design.",
                f"Engineered key workflows and automated backend logic, ensuring high reliability and maintainable architecture."
            ]
        }, None

    try:
        data = json.loads(raw_json)
        return data, None
    except Exception:
        return {"bullets": [raw_json]}, None


# ---------------------------------------------------------------------------
# Action Verbs Knowledge Base (Offline-Ready)
# ---------------------------------------------------------------------------

ACTION_VERBS = {
    "Leadership & Management": [
        "Spearheaded", "Directed", "Orchestrated", "Guided", "Championed",
        "Mentored", "Mobilized", "Fostered", "Supervised", "Coordinated"
    ],
    "Engineering & Development": [
        "Architected", "Engineered", "Implemented", "Constructed", "Deployed",
        "Integrated", "Refactored", "Automated", "Optimized", "Scaled"
    ],
    "Research & Problem Solving": [
        "Investigated", "Diagnosed", "Analyzed", "Audited", "Identified",
        "Overhauled", "Formulated", "Extracted", "Resolved", "Standardized"
    ],
    "Execution & Impact": [
        "Accelerated", "Delivered", "Maximized", "Surpassed", "Amplified",
        "Streamlined", "Boosted", "Generated", "Consolidated", "Reduced"
    ]
}

def get_action_verbs():
    """Returns curated categorized list of strong resume action verbs."""
    return ACTION_VERBS
