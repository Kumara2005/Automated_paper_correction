import streamlit as st
import pandas as pd
import utils
import auth
import time
import os
import shutil 

st.set_page_config(
    page_title="AI Paper Corrector",
    page_icon="🤖",
    layout="wide"
)

# --- Initialize Database ---
auth.init_db()

# --- Initialize Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.subject = None

# --- Diagnostics Function ---
def show_diagnostics_panel():
    """Checks and displays the status of all required components."""
    with st.sidebar.expander("🔬 System Diagnostics"):
        st.subheader("Component Status")
        
        # 1. Check Gemini API Key
        try:
            if 'GOOGLE_API_KEY' in st.secrets or 'GEMINI_API_KEY' in st.secrets:
                st.success("✅ **Gemini API Key:** Found in secrets.", icon="🔑")
            else:
                st.error("❌ **Gemini API Key:** Not found in secrets.", icon="🔑")
        except Exception:
            st.error("❌ **Gemini API Key:** `st.secrets` not configured.", icon="🔑")
            
        # 2. Check Poppler (for PDF processing)
        if shutil.which("pdftoppm"):
            st.success("✅ **Poppler (PDF):** Found and executable.", icon="📄")
        else:
            st.warning("⚠️ **Poppler (PDF):** `pdftoppm` not found in PATH.", icon="📄")
            st.caption("PDF uploads will fail. Ensure Poppler is installed and added to your system's PATH.")
            
      
        # 3. Check Local Similarity Model
        try:
            utils.get_cross_encoder() # <-- Check for the new function
            st.success("✅ **Local Model:** `CrossEncoder` loaded.", icon="🧠") # <-- Update the text
        except Exception as e:
            st.error(f"❌ **Local Model:** Failed to load. {e}", icon="🧠")
# ==================================================================
# FUNCTION DEFINITIONS
# ==================================================================

def show_teacher_dashboard():
    """Renders the dashboard for logged-in teachers."""
    st.title(f"Teacher Dashboard ({st.session_state.subject})")
    
    tab1, tab2 = st.tabs(["📝 Grade New Papers", "📊 View Subject Statistics"])
    
    with tab1:
        st.header("Grade New Student Papers")
        
        # --- MODEL SELECTION ---
        st.subheader("⚙️ Model Selection")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Fetch available models
            available_models = utils.get_available_gemini_models()
            
            if available_models:
                selected_model = st.selectbox(
                    "Choose Gemini Model for OCR and Feedback",
                    options=available_models,
                    index=0,  # Default to first (usually latest)
                    help="Select which Gemini model to use for text extraction and feedback generation. The system will automatically fall back to other models if your selection fails."
                )
                st.session_state['preferred_model'] = selected_model
                st.success(f"✅ Selected: {selected_model}")
            else:
                st.warning("⚠️ Could not fetch model list. System will use automatic fallback.")
                st.session_state['preferred_model'] = None
        
        with col2:
            st.info("💡 **Tip:** If a model fails, the system automatically tries fallback models.")
        
        st.divider()

        # --- STEP 1: ASK FOR NUMBER OF STUDENTS ---
        st.subheader("1. Select Number of Students")
        num_students = st.number_input(
            "How many students do you want to grade?", 
            min_value=1, 
            value=1,
            step=1
        )

        if num_students > 30:
            st.error("Free Tier Limit: You can only grade a maximum of 30 students at a time.")
            st.info("Please subscribe to Premium for unlimited grading.")
            st.stop()
        else:
            st.info(f"You have selected {num_students} student(s). Please fill out the form below.")


        # --- STEP 2: GET ALL NAMES, FILES, and KEY in one form ---
        st.subheader("2. Upload All Scripts and Answer Key")
            
        with st.form(key="grading_form"):
            student_data = [] # Will store dictionaries of {"name": name, "file": file}
            
            st.markdown("#### Student Details")
            # Loop to get each student's name and file
            for i in range(num_students):
                st.divider()
                st.write(f"**Student {i + 1}**")
                
                cols = st.columns(2)
                with cols[0]:
                    name = st.text_input(
                        "Student Name", 
                        key=f"name_{i}", 
                        placeholder=f"Enter name for Student {i+1}"
                    )
                with cols[1]:
                    file = st.file_uploader(
                        "Upload Answer Script", 
                        type=["pdf", "png", "jpg", "jpeg"], 
                        key=f"file_{i}"
                    )
                
                student_data.append({"name": name, "file": file})

            st.divider()
            
            # --- STEP 3: UPLOAD KEY (at the end) ---
            st.markdown("#### Teacher's Answer Key")
            st.info("📄 Upload one typed answer key (PDF, DOCX, or Image)")
            teacher_file = st.file_uploader(
                "Upload the teacher's answer key", 
                type=["pdf", "docx", "doc", "png", "jpg", "jpeg"], 
                key="teacher_key_uploader" # Use a new key
            )
            
            submit_button = st.form_submit_button("Start Grading Process", type="primary", use_container_width=True)

        if submit_button:
            # --- Validation ---
            all_fields_filled = True
            for data in student_data:
                if not data["name"] or not data["file"]:
                    all_fields_filled = False
                    break
            
            if not all_fields_filled:
                st.error("Please provide a name and upload a file for *every* student.")
                st.stop()
            
            if not teacher_file:
                st.error("Please upload the Teacher's Answer Key to proceed.")
                st.stop()

            # Get preferred model from session state
            preferred_model = st.session_state.get('preferred_model', None)

            # --- Start Grading Logic ---
            with st.spinner("Step 1/3: Processing teacher's answer key..."):
                teacher_data = utils.process_uploaded_file(teacher_file)
                
                # --- THIS IS THE UPDATED PROMPT ---
                teacher_prompt = """
                You are an expert OCR assistant. Extract all typed text from this answer key.
                The text contains questions and answers, formatted like Q1, Q2, etc.
                - **Format all question numbers clearly** at the start of a line (e.g., `Q1:`, `Q2:`, `Question 3.`).
                - **Crucially, do not mistake numbers *within* an answer (like '128-bit' or '1945') for a new question number.**
                - Maintain all original text, newlines, and formatting.
                """
                
                if isinstance(teacher_data, tuple) and teacher_data[1] == "docx":
                    teacher_text = teacher_data[0] 
                else:
                    teacher_text = utils.extract_text_from_images(teacher_data, teacher_prompt, preferred_model=preferred_model)
                
                if not teacher_text:
                    st.error("Failed to extract text from teacher's key.")
                    st.stop()
                    
                teacher_answers = utils.parse_answers(teacher_text)
                st.success(f"Step 1/3: Teacher's key processed. Found {len(teacher_answers)} question(s).")
            
            st.header("📈 Grading Results")
            overall_summary = []
            progress_bar = st.progress(0, text="Initializing grading...")
            
            for i, data in enumerate(student_data):
                student_name = data["name"]
                student_file = data["file"]
                
                st.subheader(f"Grading: {student_name}")
                
                with st.spinner(f"Step 2/3: Processing {student_name}'s script..."):
                    student_images = utils.process_uploaded_file(student_file)
                    
                    # --- THIS IS THE UPDATED PROMPT ---
                    student_prompt = """
                    You are an expert at transcribing handwritten text.
                    The text contains student answers to questions, often numbered.
                    - **Identify and format all question numbers clearly** at the start of a line (e.g., `Q1:`, `Answer 2.`).
                    - **Crucially, do not mistake numbers *within* an answer (like '128' or '10%') for a new question number.**
                    - Transcribe the rest of the handwriting as accurately as possible, preserving newlines.
                    """
                    
                    student_text = utils.extract_text_from_images(student_images, student_prompt, preferred_model=preferred_model)
                    
                    if not student_text:
                        st.warning(f"Could not extract text for {student_name}. Skipping.")
                        continue
                        
                    student_answers = utils.parse_answers(student_text)
                
                with st.spinner(f"Step 3/3: Comparing and scoring {student_name}..."):
                    results, total, max_s = utils.grade_paper_locally(teacher_answers, student_answers)
                    
                    percentage = (total / max_s) * 100 if max_s > 0 else 0
                    results_df = pd.DataFrame(results)
                    
                    overall_feedback = utils.get_overall_feedback(student_name, st.session_state.subject, total, max_s, results_df, preferred_model=preferred_model)
                    
                    summary = {
                        "total_score": total,
                        "max_score": max_s,
                        "percentage": round(percentage, 2),
                        "overall_feedback": overall_feedback
                    }
                    
                    utils.save_results_to_db(
                        student_name=student_name, 
                        subject=st.session_state.subject,
                        teacher_username=st.session_state.username,
                        summary=summary,
                        detailed_breakdown=results
                    )
                    
                    st.metric(label="Score", value=f"{total} / {max_s}", delta=f"{percentage:.1f}%")
                    st.caption("Overall Feedback:")
                    st.info(overall_feedback)
                    
                    with st.expander("View Detailed Breakdown"):
                        st.dataframe(results_df, use_container_width=True, hide_index=True)
                    
                    overall_summary.append({
                        "Student": student_name, 
                        "Score": f"{total}/{max_s}", 
                        "Percentage": f"{percentage:.1f}%"
                    })
                
                progress_bar.progress((i + 1) / num_students, text=f"Graded {student_name}")
            
            st.success("All papers graded successfully!")
            st.balloons()
            
            st.header("Batch Summary")
            st.dataframe(pd.DataFrame(overall_summary), use_container_width=True, hide_index=True)

    with tab2:
        st.header("📊 Student Statistics")
        st.info(f"Showing all saved results for your subject: **{st.session_state.subject}**")
        
        results_df = utils.get_teacher_results(st.session_state.subject)
        
        if results_df.empty:
            st.warning("No results found for this subject yet.")
        else:
            st.subheader("Download All Data")
            json_data = utils.export_teacher_data_to_json(st.session_state.subject)
            
            st.download_button(
                label="📥 Export All Subject Data to JSON",
                data=json_data,
                file_name=f"{st.session_state.subject}_all_grades.json",
                mime="application/json",
                use_container_width=True
            )
            st.divider() 

            display_cols = [col for col in results_df.columns if col != 'id']
            st.dataframe(results_df[display_cols], use_container_width=True, hide_index=True)
            
            st.subheader("View Detailed Breakdown")
            result_ids = results_df['id'].tolist()
            options = [f"{row['student_name']} - {row['timestamp']} (Score: {row['total_score']}/{row['max_score']})" for _, row in results_df.iterrows()]
            
            selected_option = st.selectbox("Select a result to view details:", options, index=None, placeholder="Select a result...")
            
            if selected_option:
                selected_index = options.index(selected_option)
                selected_result_id = result_ids[selected_index]
                
                detailed_df = utils.get_detailed_result_by_id(selected_result_id)
                st.dataframe(detailed_df, use_container_width=True, hide_index=True)


def show_student_dashboard():
    """Renders the dashboard for logged-in students."""
    st.title("📚 My Student Dashboard")
    st.header(f"My Graded Papers")
    
    results_df = utils.get_student_results(st.session_state.username)
    
    if results_df.empty:
        st.warning("You do not have any graded papers yet.")
    else:
        st.info("Here are all your graded papers. Select one to see the detailed feedback.")
        
        display_cols = [col for col in results_df.columns if col != 'id']
        st.dataframe(
            results_df[display_cols], 
            use_container_width=True, 
            hide_index=True
        )
        
        st.subheader("View Detailed Breakdown")
        result_ids = results_df['id'].tolist()
        options = [f"{row['subject']} - {row['timestamp']} (Score: {row['total_score']}/{row['max_score']})" for _, row in results_df.iterrows()]
        
        selected_option = st.selectbox("Select a result to view details:", options, index=None, placeholder="Select a result...")
        
        if selected_option:
            selected_index = options.index(selected_option)
            selected_result_id = result_ids[selected_index]
            
            detailed_df = utils.get_detailed_result_by_id(selected_result_id)
            st.dataframe(detailed_df, use_container_width=True, hide_index=True)


# --- Main App Logic ---

if not st.session_state.logged_in:
    auth.render_login_page()
else:
    # --- Logged-in User Interface ---
    st.sidebar.title(f"Welcome, {st.session_state.username}")
    st.sidebar.caption(f"Role: **{st.session_state.role.title()}**")
    
    if st.session_state.role == 'teacher':
        st.sidebar.caption(f"Managing Subject: **{st.session_state.subject}**")
    
    show_diagnostics_panel() 
    st.sidebar.button("Logout", use_container_width=True, on_click=auth.handle_logout)

    # --- Role-Based Dashboards ---
    if st.session_state.role == 'teacher':
        show_teacher_dashboard()
    else:
        show_student_dashboard()