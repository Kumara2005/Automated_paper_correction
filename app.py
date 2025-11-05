import streamlit as st
import pandas as pd
import utils
import auth
import time
import os

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


def show_teacher_dashboard():
    """Renders the dashboard for logged-in teachers."""
    st.title(f"Teacher Dashboard ({st.session_state.subject})")
    
    tab1, tab2 = st.tabs(["📝 Grade New Papers", "📊 View Subject Statistics"])
    
    with tab1:
        st.header("Grade New Student Papers")
        
        with st.form(key="grading_form"):
            st.subheader("1. Upload Answer Key")
            st.info("📄 Upload one typed answer key (PDF, DOCX, or Image)")
            teacher_file = st.file_uploader(
                "Upload the teacher's answer key", 
                type=["pdf", "docx", "doc", "png", "jpg", "jpeg"], 
                key="teacher"
            )
            
            st.subheader("2. Upload Student Scripts")
            st.info("✍️ Upload handwritten answers (PDF or Image). You can select multiple files.")
            student_files = st.file_uploader(
                "Upload student answer scripts", 
                type=["pdf", "png", "jpg", "jpeg"], 
                key="student",
                accept_multiple_files=True
            )
            
            submit_button = st.form_submit_button("Start Grading Process", type="primary", use_container_width=True)

        if submit_button:
            # --- Input Validation ---
            if not teacher_file or not student_files:
                st.error("Please upload both an answer key and at least one student script.")
                st.stop()
            
            if len(student_files) > 30:
                st.error("Free Tier Limit: You can only upload a maximum of 30 student scripts at a time.")
                st.info("Contact us to subscribe to Premium for unlimited grading.")
                st.stop()
                
            # --- 1. Process Teacher Key ---
            with st.spinner("Step 1/3: Processing teacher's answer key..."):
                teacher_data = utils.process_uploaded_file(teacher_file)
                
                if isinstance(teacher_data, tuple) and teacher_data[1] == "docx":
                    teacher_text = teacher_data[0] # Text already extracted
                else:
                    teacher_text = utils.extract_text_from_images(teacher_data, "Extract all typed text.")
                
                if not teacher_text:
                    st.error("Failed to extract text from teacher's key.")
                    st.stop()
                    
                teacher_answers = utils.parse_answers(teacher_text)
                st.success(f"Step 1/3: Teacher's key processed. Found {len(teacher_answers)} question(s).")
            
            st.header("📈 Grading Results")
            overall_summary = []
            
            # --- 2. Process Each Student ---
            progress_bar = st.progress(0, text="Initializing grading...")
            
            for i, student_file in enumerate(student_files):
                student_name = os.path.splitext(student_file.name)[0] # Get name from filename
                st.subheader(f"Grading: {student_name}")
                
                with st.spinner(f"Step 2/3: Processing {student_name}'s script..."):
                    student_images = utils.process_uploaded_file(student_file)
                    student_text = utils.extract_text_from_images(student_images, "Transcribe all handwritten text.")
                    
                    if not student_text:
                        st.warning(f"Could not extract text for {student_name}. Skipping.")
                        continue
                        
                    student_answers = utils.parse_answers(student_text)
                
                with st.spinner(f"Step 3/3: Comparing and scoring {student_name}..."):
                    # Use LOCAL comparison (no API)
                    results, total, max_s = utils.grade_paper_locally(teacher_answers, student_answers)
                    
                    percentage = (total / max_s) * 100 if max_s > 0 else 0
                    results_df = pd.DataFrame(results)
                    
                    # Use Gemini for OVERALL feedback
                    overall_feedback = utils.get_overall_feedback(student_name, st.session_state.subject, total, max_s, results_df)
                    
                    summary = {
                        "total_score": total,
                        "max_score": max_s,
                        "percentage": round(percentage, 2),
                        "overall_feedback": overall_feedback
                    }
                    
                    # Save to DB
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
                
                progress_bar.progress((i + 1) / len(student_files), text=f"Graded {student_name}")
            
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
            st.dataframe(results_df.drop(columns=['id']), use_container_width=True, hide_index=True)
            
            st.subheader("View Detailed Breakdown")
            result_ids = results_df['id'].tolist()
            options = [f"{row['student_name']} ({row['timestamp']})" for _, row in results_df.iterrows()]
            
            selected_option = st.selectbox("Select a result to view details:", options)
            
            if selected_option:
                selected_index = options.index(selected_option)
                selected_result_id = result_ids[selected_index]
                
                detailed_df = utils.get_detailed_result_by_id(selected_result_id)
                st.dataframe(detailed_df, use_container_width=True, hide_index=True)


def show_student_dashboard():
    """Renders the dashboard for logged-in students."""
    st.title("📚 My Student Dashboard")
    st.header(f"My Graded Papers")
    st.info("Here you can see all your graded papers. You cannot see results from other students.")

    results_df = utils.get_student_results(st.session_state.username)
    
    if results_df.empty:
        st.warning("You do not have any graded papers yet.")
    else:
        st.dataframe(
            results_df.drop(columns=['id']), 
            use_container_width=True, 
            hide_index=True
        )
        
        st.subheader("View Detailed Breakdown")
        result_ids = results_df['id'].tolist()
        options = [f"{row['subject']} ({row['timestamp']})" for _, row in results_df.iterrows()]
        
        selected_option = st.selectbox("Select a result to view details:", options)
        
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
    st.sidebar.caption(f"Subject: **{st.session_state.subject}**")
    if st.sidebar.button("Logout", use_container_width=True):
        auth.handle_logout()

    # --- Role-Based Dashboards ---
    if st.session_state.role == 'teacher':
        show_teacher_dashboard()
    else:
        show_student_dashboard()
import streamlit as st
import utils
import time
import pandas as pd

st.set_page_config(
    page_title="AI Paper Corrector",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI-Powered Automated Paper Corrector")
st.write("Upload teacher's answer key (PDF, DOCX, or Images) and student's handwritten answer script (PDF or Images: PNG, JPG) for AI-powered grading and evaluation.")

utils.configure_api()

import streamlit as st
import pandas as pd
import utils
import auth
import time
import os

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


def show_teacher_dashboard():
    """Renders the dashboard for logged-in teachers."""
    st.title(f"Teacher Dashboard ({st.session_state.subject})")
    
    tab1, tab2 = st.tabs(["📝 Grade New Papers", "📊 View Subject Statistics"])
    
    with tab1:
        st.header("Grade New Student Papers")
        
        with st.form(key="grading_form"):
            st.subheader("1. Upload Answer Key")
            st.info("📄 Upload one typed answer key (PDF, DOCX, or Image)")
            teacher_file = st.file_uploader(
                "Upload the teacher's answer key", 
                type=["pdf", "docx", "doc", "png", "jpg", "jpeg"], 
                key="teacher"
            )
            
            st.subheader("2. Upload Student Scripts")
            st.info("✍️ Upload handwritten answers (PDF or Image). You can select multiple files.")
            student_files = st.file_uploader(
                "Upload student answer scripts", 
                type=["pdf", "png", "jpg", "jpeg"], 
                key="student",
                accept_multiple_files=True
            )
            
            submit_button = st.form_submit_button("Start Grading Process", type="primary", use_container_width=True)

        if submit_button:
            # --- Input Validation ---
            if not teacher_file or not student_files:
                st.error("Please upload both an answer key and at least one student script.")
                st.stop()
            
            if len(student_files) > 30:
                st.error("Free Tier Limit: You can only upload a maximum of 30 student scripts at a time.")
                st.info("Contact us to subscribe to Premium for unlimited grading.")
                st.stop()
                
            # --- 1. Process Teacher Key ---
            with st.spinner("Step 1/3: Processing teacher's answer key..."):
                teacher_data = utils.process_uploaded_file(teacher_file)
                
                if isinstance(teacher_data, tuple) and teacher_data[1] == "docx":
                    teacher_text = teacher_data[0] # Text already extracted
                else:
                    teacher_text = utils.extract_text_from_images(teacher_data, "Extract all typed text.")
                
                if not teacher_text:
                    st.error("Failed to extract text from teacher's key.")
                    st.stop()
                    
                teacher_answers = utils.parse_answers(teacher_text)
                st.success(f"Step 1/3: Teacher's key processed. Found {len(teacher_answers)} question(s).")
            
            st.header("📈 Grading Results")
            overall_summary = []
            
            # --- 2. Process Each Student ---
            progress_bar = st.progress(0, text="Initializing grading...")
            
            for i, student_file in enumerate(student_files):
                student_name = os.path.splitext(student_file.name)[0] # Get name from filename
                st.subheader(f"Grading: {student_name}")
                
                with st.spinner(f"Step 2/3: Processing {student_name}'s script..."):
                    student_images = utils.process_uploaded_file(student_file)
                    student_text = utils.extract_text_from_images(student_images, "Transcribe all handwritten text.")
                    
                    if not student_text:
                        st.warning(f"Could not extract text for {student_name}. Skipping.")
                        continue
                        
                    student_answers = utils.parse_answers(student_text)
                
                with st.spinner(f"Step 3/3: Comparing and scoring {student_name}..."):
                    # Use LOCAL comparison (no API)
                    results, total, max_s = utils.grade_paper_locally(teacher_answers, student_answers)
                    
                    percentage = (total / max_s) * 100 if max_s > 0 else 0
                    results_df = pd.DataFrame(results)
                    
                    # Use Gemini for OVERALL feedback
                    overall_feedback = utils.get_overall_feedback(student_name, st.session_state.subject, total, max_s, results_df)
                    
                    summary = {
                        "total_score": total,
                        "max_score": max_s,
                        "percentage": round(percentage, 2),
                        "overall_feedback": overall_feedback
                    }
                    
                    # Save to DB
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
                
                progress_bar.progress((i + 1) / len(student_files), text=f"Graded {student_name}")
            
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
            st.dataframe(results_df.drop(columns=['id']), use_container_width=True, hide_index=True)
            
            st.subheader("View Detailed Breakdown")
            result_ids = results_df['id'].tolist()
            options = [f"{row['student_name']} ({row['timestamp']})" for _, row in results_df.iterrows()]
            
            selected_option = st.selectbox("Select a result to view details:", options)
            
            if selected_option:
                selected_index = options.index(selected_option)
                selected_result_id = result_ids[selected_index]
                
                detailed_df = utils.get_detailed_result_by_id(selected_result_id)
                st.dataframe(detailed_df, use_container_width=True, hide_index=True)


def show_student_dashboard():
    """Renders the dashboard for logged-in students."""
    st.title("📚 My Student Dashboard")
    st.header(f"My Graded Papers")
    st.info("Here you can see all your graded papers. You cannot see results from other students.")

    results_df = utils.get_student_results(st.session_state.username)
    
    if results_df.empty:
        st.warning("You do not have any graded papers yet.")
    else:
        st.dataframe(
            results_df.drop(columns=['id']), 
            use_container_width=True, 
            hide_index=True
        )
        
        st.subheader("View Detailed Breakdown")
        result_ids = results_df['id'].tolist()
        options = [f"{row['subject']} ({row['timestamp']})" for _, row in results_df.iterrows()]
        
        selected_option = st.selectbox("Select a result to view details:", options)
        
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
    st.sidebar.caption(f"Subject: **{st.session_state.subject}**")
    if st.sidebar.button("Logout", use_container_width=True):
        auth.handle_logout()

    # --- Role-Based Dashboards ---
    if st.session_state.role == 'teacher':
        show_teacher_dashboard()
    else:
        show_student_dashboard()
