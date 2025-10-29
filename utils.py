import streamlit as st
import google.generativeai as genai
import pymupdf
from PIL import Image
from docx import Document
import io
import re
import json
import os
import glob
import time

MODEL_NAME = "gemini-2.5-flash"

def configure_api():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except KeyError:
        st.error("GEMINI_API_KEY not found in .streamlit/secrets.toml")
        st.stop()
    except Exception as e:
        st.error(f"Error configuring API: {e}")
        st.stop()

def pdf_to_images(pdf_file_bytes):
    images = []
    try:
        pdf_doc = pymupdf.open(stream=pdf_file_bytes, filetype="pdf")
        for page_num in range(len(pdf_doc)):
            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))
            images.append(image)
        pdf_doc.close()
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return None
    return images

def extract_text_from_docx(docx_file):
    """
    Extract text from a DOCX file.
    Returns the extracted text as a string.
    """
    try:
        doc = Document(docx_file)
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)
        return "\n".join(text)
    except Exception as e:
        st.error(f"Error processing DOCX file: {e}")
        return None

def process_uploaded_file(uploaded_file, file_purpose="general"):
    """
    Process uploaded file - can be PDF, image (PNG, JPG, JPEG), or DOCX
    
    Args:
        uploaded_file: The uploaded file object
        file_purpose: "teacher" for teacher files (supports DOCX), "student" for student files (images only)
    
    Returns:
        For images/PDFs: list of PIL Image objects
        For DOCX: tuple of (text_string, "docx")
    """
    file_type = uploaded_file.type
    
    try:
        if file_type == "application/pdf":
            # Process PDF
            pdf_bytes = uploaded_file.getvalue()
            images = pdf_to_images(pdf_bytes)
            return images
        elif file_type in ["image/png", "image/jpeg", "image/jpg"]:
            # Process image directly
            image = Image.open(uploaded_file)
            return [image]
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            # Process DOCX file (only for teacher files)
            if file_purpose == "teacher":
                text = extract_text_from_docx(uploaded_file)
                if text:
                    return (text, "docx")
                else:
                    return None
            else:
                st.error("Word documents are only supported for teacher answer keys, not student submissions.")
                return None
        else:
            st.error(f"Unsupported file type: {file_type}")
            return None
    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

def extract_text_from_images(images, prompt):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        content_parts = [prompt]
        for img in images:
            content_parts.append(img)
        response = model.generate_content(content_parts)
        return response.text
    except Exception as e:
        st.error(f"Error calling Gemini API: {e}")
        return None

def parse_answers(text):
    questions = re.split(r'\b(Q\d+|\d+)[.)]\s*', text.strip())
    answers = {}
    if len(questions) > 1:
        for i in range(1, len(questions), 2):
            try:
                q_num = questions[i].replace("Q", "").strip()
                answer_text = questions[i+1].strip()
                if q_num and answer_text:
                    answers[q_num] = answer_text
            except IndexError:
                continue
    if not answers:
        st.warning("Could not parse numbered answers. Treating as one block.")
        answers["1"] = text
    return answers

def get_score_and_feedback(teacher_answer, student_answer):
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f'''You are an AI grading assistant.
Teacher Answer: "{teacher_answer}"
Student Answer: "{student_answer}"

Provide score 0-10 and feedback. Return ONLY valid JSON:
{{"score": <number>, "feedback": "<text>"}}'''
    
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(json_text)
    except Exception as e:
        st.error(f"Error scoring: {e}")
        return {"score": 0, "feedback": "Error in API response"}

def save_results_to_json(student_name, subject, results_data, summary):
    try:
        if not os.path.exists("results"):
            os.makedirs("results")
        clean_name = student_name.lower().replace(" ", "_")
        clean_subject = subject.lower().replace(" ", "_")
        filename = f"{clean_name}_{clean_subject}.json"
        filepath = os.path.join("results", filename)
        data = {
            "student_name": student_name,
            "subject": subject,
            "summary": summary,
            "detailed_breakdown": results_data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath
    except Exception as e:
        st.error(f"Error saving results: {e}")
        return None

def load_all_results():
    all_results = []
    try:
        if not os.path.exists("results"):
            return all_results
        json_files = glob.glob(os.path.join("results", "*.json"))
        for filepath in json_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_results.append(data)
            except Exception as e:
                st.warning(f"Could not load {filepath}: {e}")
                continue
        return all_results
    except Exception as e:
        st.error(f"Error loading results: {e}")
        return all_results
