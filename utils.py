import streamlit as st
import google.generativeai as genai
from sentence_transformers import SentenceTransformer, util
import sqlite3
import pandas as pd
from datetime import datetime
import re
import io
import os


# --- File Processing & AI Configuration ---

@st.cache_resource
def get_sentence_transformer():
    """Loads and caches the local sentence transformer model."""
    return SentenceTransformer('all-MiniLM-L6-v2')

@st.cache_resource
def get_gemini_model():
    """Configures and caches the Gemini model."""
    try:
        # Support both key names for compatibility
        api_key = None
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
        elif "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]

        if not api_key:
            raise RuntimeError("No API key found in st.secrets (GOOGLE_API_KEY or GEMINI_API_KEY)")

        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-pro')
    except Exception as e:
        st.error(f"Error configuring Gemini API. Make sure an API key is in st.secrets. {e}")
        return None


# --- Text Extraction (using Gemini) ---

def process_uploaded_file(uploaded_file):
    """Converts PDF, DOCX, or Image files into a list of PIL Images or text."""
    from pdf2image import convert_from_bytes
    from PIL import Image
    from docx import Document

    file_type = uploaded_file.type

    if file_type == "application/pdf":
        images = convert_from_bytes(uploaded_file.read())
        return [img.convert("RGB") for img in images]
    elif file_type in ["image/png", "image/jpeg", "image/jpg"]:
        image = Image.open(uploaded_file).convert("RGB")
        return [image]
    elif "document" in file_type or "word" in file_type or file_type.endswith("docx"):
        # Extract DOCX text using python-docx
        try:
            doc = Document(uploaded_file)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return ("\n".join(paragraphs), "docx")
        except Exception:
            return None
    return None

def extract_text_from_images(images: list, prompt: str):
    """Uses Gemini to extract text (OCR) from a list of images."""
    model = get_gemini_model()
    if not model:
        return None
        
    try:
        # The genai library often accepts images directly; provide prompt + images
        content_parts = [prompt]
        content_parts.extend(images)
        response = model.generate_content(content_parts)
        return response.text
    except Exception as e:
        st.error(f"Error during text extraction: {e}")
        return None


def parse_answers(text: str):
    """Parses extracted text into a dictionary of {question_num: answer_text}."""
    pattern = re.compile(r"(?i)(?:Q|Question)?\s*(\d+)\s*[:.)-]\s*(.*)", re.MULTILINE)
    matches = list(pattern.finditer(text))
    
    if not matches:
        return {"1": text.strip()}

    answers = {}
    last_pos = None
    last_num = None
    for match in matches:
        q_num = match.group(1).strip()
        start = match.start(2)
        if last_pos is not None and last_num is not None:
            answers[last_num] = text[last_pos:match.start()].strip()
        last_num = q_num
        last_pos = start

    if last_num is not None:
        answers[last_num] = text[last_pos:].strip()

    return answers


# --- Local Scoring (No API) ---

def get_local_similarity(text1, text2):
    """Calculates cosine similarity between two texts using a local model."""
    if not text1 or not text2:
        return 0.0
        
    model = get_sentence_transformer()
    
    try:
        embedding1 = model.encode(text1, convert_to_tensor=True)
        embedding2 = model.encode(text2, convert_to_tensor=True)
        
        cosine_score = util.cos_sim(embedding1, embedding2)
        return float(cosine_score.item())
    except Exception as e:
        st.warning(f"Error calculating similarity: {e}")
        return 0.0

def grade_paper_locally(teacher_answers: dict, student_answers: dict):
    """Grades a paper using local similarity, no Gemini API for scoring."""
    results = []
    total_score = 0
    max_score = 0
    
    for q_num, t_answer in teacher_answers.items():
        s_answer = student_answers.get(q_num, "No answer found.")
        
        similarity = get_local_similarity(t_answer, s_answer)
        
        score = round(similarity * 10)
        
        if score >= 9:
            feedback = "Excellent. The answer is correct and complete."
        elif score >= 7:
            feedback = "Good. The answer captures the main points."
        elif score >= 5:
            feedback = "Partial. The answer is missing key concepts."
        else:
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
                    summary.get('overall_feedback', ''),
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

