import os
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b"
]

def generate_questions(keywords):
    if not keywords:
        return []

    prompt = (
        f"Generate exactly 5 technical interview questions based on the following skills: "
        f"{', '.join(keywords)}.\n\n"
        "Rules:\n"
        "1. Output ONLY a numbered list (1., 2., 3., etc.).\n"
        "2. Each question must be a single sentence.\n"
        "3. Do NOT include explanations, code, or multi-paragraph answers.\n"
        "4. Do NOT add introductions like 'Here are the questions'."
    )

    for model_name in MODELS:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an expert technical interviewer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )

            raw_output = response.choices[0].message.content
            if not raw_output:
                continue

            # Extract only numbered lines and truncate to first sentence
            questions = []
            for line in raw_output.split("\n"):
                line = line.strip()
                if line and line[0].isdigit():
                    # Take only the first sentence (up to first '?', or first '.')
                    if "?" in line:
                        first_sentence = line.split("?")[0] + "?"
                    else:
                        first_sentence = line.split(".")[0] + "?"
                    questions.append(first_sentence)

            if questions:
                return questions
        except Exception as e:
            print(f"Error with model {model_name}: {e}")
            continue

    return []
