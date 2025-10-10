# question_generator.py
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_questions(keywords):
    prompt = f"Generate 5 technical interview questions based on the following skills: {', '.join(keywords)}."
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # ✅ latest and supported model
        messages=[
            {"role": "system", "content": "You are an expert technical interviewer."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400,
        temperature=0.7
    )
    
    return response.choices[0].message.content

