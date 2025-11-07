import streamlit as st
import google.generativeai as genai
# --- CHANGED: We now also import CrossEncoder ---
from sentence_transformers import SentenceTransformer, util
from sentence_transformers.cross_encoder import CrossEncoder 
import sqlite3
import pandas as pd
from datetime import datetime
import re
import io
import json

import time
import traceback
# --- File Processing & AI Configuration ---

@st.cache_resource
def get_sentence_transformer():
    """Loads and caches the local sentence transformer model."""
    # This is still used by get_local_similarity, which we are now NOT using for grading
    return SentenceTransformer('all-MiniLM-L6-v2')

# --- NEW: Function to load the new, more accurate model ---
@st.cache_resource
def get_cross_encoder():
    """Load and cache a CrossEncoder model for pairwise scoring."""
    try:
        # Use a compact but accurate CrossEncoder; adjust if you prefer another model
        return CrossEncoder('cross-encoder/stsb-roberta-base')
    except Exception as e:
        st.error(f"Failed to load CrossEncoder model: {e}")
        return None

@st.cache_resource
def get_gemini_model():
    """Configures and returns a Gemini generative model instance.

    The function reads the API key from `st.secrets` (GOOGLE_API_KEY or GEMINI_API_KEY).
    It configures the `google.generativeai` client and returns a configured GenerativeModel.
    """
    try:
        api_key = None
        if 'GOOGLE_API_KEY' in st.secrets:
            api_key = st.secrets['GOOGLE_API_KEY']
        elif 'GEMINI_API_KEY' in st.secrets:
            api_key = st.secrets['GEMINI_API_KEY']

        if not api_key:
            raise RuntimeError('No API key found in st.secrets (GOOGLE_API_KEY or GEMINI_API_KEY)')

        genai.configure(api_key=api_key)
        # Use a generic 'pro' alias; change if you want a different exact model name
        return genai.GenerativeModel('models/gemini-pro-latest')
    except Exception as e:
        st.error(f"Error configuring Gemini API: {e}")
        return None
def process_uploaded_file(uploaded_file):
    """Converts PDF, DOCX, or Image files into a list of PIL Images or text."""
    from pdf2image import convert_from_bytes
    from PIL import Image
    import docx2txt

    file_type = uploaded_file.type
    
    if file_type == "application/pdf":
        images = convert_from_bytes(uploaded_file.read())
        return [img.convert("RGB") for img in images]
    elif file_type in ["image/png", "image/jpeg", "image/jpg"]:
        image = Image.open(uploaded_file).convert("RGB")
        return [image]
    elif "document" in file_type or "doc" in file_type:
        text = docx2txt.process(uploaded_file)
        return (text, "docx") # Return text directly for DOCX
    return None

def extract_text_from_images(images: list, prompt: str):
    """Uses Gemini to extract text (OCR) from a list of images."""
    # Configure Gemini model locally to avoid potential lookup issues
    api_key = None
    try:
        if 'GOOGLE_API_KEY' in st.secrets:
            api_key = st.secrets['GOOGLE_API_KEY']
        elif 'GEMINI_API_KEY' in st.secrets:
            api_key = st.secrets['GEMINI_API_KEY']
    except Exception:
        api_key = None

    if not api_key:
        st.error('No Gemini API key found in st.secrets; cannot perform remote OCR.')
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/gemini-pro-latest')
    except Exception as e:
        st.error(f'Could not configure Gemini model: {e}')
        return None
        
    try:
        image_parts = []
        for img in images:
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            image_parts.append({
                "mime_type": "image/jpeg",
                "data": img_byte_arr.getvalue()
            })
            
        response = model.generate_content([prompt] + image_parts)
        return response.text
    except Exception as e:
        st.error(f"Error during text extraction: {e}")
        return None

def parse_answers(text: str):
    """Parses extracted text into a dictionary of {question_num: answer_text}."""
    # Use inline flags (?i) for case-insensitive and (?m) for multiline to avoid relying
    # on the re module constants (prevents environment-specific attribute issues).
    # This is the corrected line
    # Match question numbers at the start of lines, case-insensitive and multiline
    pattern = re.compile(r"^(?:Q|Question)?\s*(\d+)\s*[:.)-]\s*(.*)", re.MULTILINE | re.IGNORECASE)
    matches = pattern.finditer(text)
    
    answers = {}
    last_pos = -1
    last_num = -1
    
    match_list = list(matches)
    
    if not match_list:
        return {"1": text.strip()}

    for i, match in enumerate(match_list):
        q_num = match.group(1).strip()
        answer_start = match.start(2)
        
        if last_pos != -1:
            answer_text = text[last_pos:match.start()].strip()
            answers[last_num] = answer_text
            
        last_num = q_num
        last_pos = answer_start

    if last_num != -1:
        answer_text = text[last_pos:].strip()
        answers[last_num] = answer_text

    return answers

# --- Local Scoring (No API) ---

# This function is no longer used for grading but we can keep it
def get_local_similarity(text1, text2):
    """Calculates cosine similarity between two texts using a local model."""
    if not text1 or not text2:
        return 0.0
        
    model = get_sentence_transformer()
    
    try:
        embedding1 = model.encode(text1, convert_to_tensor=True)
        embedding2 = model.encode(text2, convert_to_tensor=True)
        
        cosine_score = util.cos_sim(embedding1, embedding2)
        return cosine_score.item()
    except Exception as e:
        st.warning(f"Error calculating similarity: {e}")
        return 0.0

# --- UPDATED GRADING FUNCTION ---
def grade_paper_locally(teacher_answers: dict, student_answers: dict):
    """Grades a paper using a CrossEncoder for accurate similarity scoring."""
    results = []
    total_score = 0
    max_score = 0
    
    # Load the new, more accurate model
    model = get_cross_encoder()
    
    for q_num, t_answer in teacher_answers.items():
        s_answer = student_answers.get(q_num, "No answer found.")
        
        # --- NEW SCORING METHOD ---
        # A CrossEncoder compares both sentences at the same time
        # It is much more accurate for scoring tasks.
        # It outputs a score from 0.0 (no match) to 1.0 (perfect match)
        
        if s_answer == "No answer found.":
            similarity = 0.0
        else:
            similarity = model.predict([t_answer, s_answer])

        # We will use stricter conditions to convert the score to a grade
        # This new 'similarity' score will be much more accurate.
        # "IPv6: it has" will now get a very low score (e.g., 0.1)
        
        if similarity >= 0.9:
            score = 10
            feedback = "Excellent. The answer is correct and complete."
        elif similarity >= 0.8:
            score = 8
            feedback = "Very Good. The answer captures all main points."
        elif similarity >= 0.7:
            score = 7
            feedback = "Good. The answer captures the main points, but lacks some detail."
        elif similarity >= 0.6: 
            score = 5
            feedback = "Partial. The answer is missing key concepts."
        else:
            # Anything below 60% similarity (like "IPv6: it has") is a 0.
            score = 0
            feedback = "Incorrect. The answer does not match the key."
            
        results.append({
            "Question": q_num,
            "Teacher's Answer": t_answer,
            "Student's Answer": s_answer,
            "Score": f"{score}/10",
            "Feedback": feedback
        })
        
        total_score += score
        max_score += 10
        
    return results, total_score, max_score

# --- Overall Feedback (using Gemini) ---

def get_overall_feedback(student_name, subject, total_score, max_score, results_df):
    """Uses Gemini to generate a final summary feedback for the student."""
    model = get_gemini_model()
    if not model:
        return "Could not generate AI feedback."

    st.write("Generating overall AI feedback...")
    prompt = f"""
    You are an expert teacher. A student named {student_name} has just completed an exam in {subject}.
    Their final score was {total_score} out of {max_score}.
    
    Here is the question-by-question breakdown:
    {results_df.to_string(index=False)}
    
    Please provide a brief, overall feedback summary for the student (no more than 3-4 sentences). 
    Focus on their strengths and one or two key areas for improvement. 
    Be encouraging and constructive. Address the student directly as 'you'.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error generating overall feedback: {e}")
        return "Failed to generate AI feedback."


# --- Database Operations ---

def save_results_to_db(student_name, subject, teacher_username, summary, detailed_breakdown):
    """Saves a student's complete result to the database."""
    try:
        with sqlite3.connect('results_db.sqlite') as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO results (student_name, subject, teacher_username, total_score, max_score, percentage, overall_feedback, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_name,
                    subject,
                    teacher_username,
                    summary['total_score'],
                    summary['max_score'],
                    summary['percentage'],
                    summary['overall_feedback'],
                    datetime.now()
                )
            )
            
            result_id = cursor.lastrowid
            
            for item in detailed_breakdown:
                cursor.execute(
                    """
                    INSERT INTO detailed_results (result_id, question, teacher_answer, student_answer, score_str, feedback)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id,
                        item['Question'],
                        item["Teacher's Answer"],
                        item["Student's Answer"],
                        item["Score"],
                        item["Feedback"]
                    )
                )
            
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Database save error: {e}")
        return False

def get_student_results(username: str):
    """Fetches all results for a specific student."""
    with sqlite3.connect('results_db.sqlite') as conn:
        query = """
        SELECT subject, total_score, max_score, percentage, overall_feedback, timestamp, id 
        FROM results 
        WHERE student_name = ?
        ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn, params=(username,))
        return df

def get_teacher_results(subject: str):
    """Fetches all results for a specific subject (for the teacher)."""
    with sqlite3.connect('results_db.sqlite') as conn:
        query = """
        SELECT student_name, total_score, max_score, percentage, overall_feedback, timestamp, id 
        FROM results 
        WHERE subject = ?
        ORDER BY student_name, timestamp DESC
        """
        df = pd.read_sql_query(query, conn, params=(subject,))
        return df

def get_detailed_result_by_id(result_id: int):
    """Fetches the detailed question-by-question breakdown for a single result."""
    with sqlite3.connect('results_db.sqlite') as conn:
        query = """
        SELECT question AS "Question", 
               teacher_answer AS "Teacher's Answer",
               student_answer AS "Student's Answer",
               score_str AS "Score",
               feedback AS "Feedback"
        FROM detailed_results 
        WHERE result_id = ?
        """
        df = pd.read_sql_query(query, conn, params=(result_id,))
        return df

# --- NEW FUNCTION TO EXPORT JSON ---

def export_teacher_data_to_json(subject: str):
    """Fetches all results for a subject and formats as a JSON string."""
    
    summary_df = get_teacher_results(subject) 
    
    if summary_df.empty:
        return json.dumps({"error": "No data found for this subject."}, indent=2)

    all_data = []
    
    for _, row in summary_df.iterrows():
        result_id = row['id']
        detailed_df = get_detailed_result_by_id(result_id)
        
        entry = {
            "student_name": row['student_name'],
            "subject": subject,
            "summary": {
                "total_score": row['total_score'],
                "max_score": row['max_score'],
                "percentage": row['percentage']
            },
            "detailed_breakdown": detailed_df.to_dict('records'), 
            "overall_feedback": row['overall_feedback'],
            "timestamp": row['timestamp']
        }
        all_data.append(entry)
    
    return json.dumps(all_data, indent=2, default=str)