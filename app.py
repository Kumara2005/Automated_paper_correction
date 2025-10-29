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

tab1, tab2 = st.tabs(["📝 Grade New Paper", "📊 View Student Statistics"])

with tab1:
    st.header("Grade New Paper")
    
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        student_name = st.text_input("Student Name", placeholder="e.g., John Doe")
    with col_info2:
        subject = st.text_input("Subject", placeholder="e.g., Math Quiz")
    
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Teacher's Answer Key")
        st.info("📄 Upload typed answer key (PDF, DOCX, or Image)")
        teacher_file = st.file_uploader(
            "Upload the teacher's answer key", 
            type=["pdf", "docx", "doc", "png", "jpg", "jpeg"], 
            key="teacher"
        )

    with col2:
        st.subheader("2. Student's Answer Script")
        st.info("✍️ Upload handwritten answers (PDF or Image)")
        student_file = st.file_uploader(
            "Upload the student's answer script", 
            type=["pdf", "png", "jpg", "jpeg"], 
            key="student"
        )

    if st.button("Start Grading Process", type="primary", use_container_width=True):
        if not student_name or not subject:
            st.error("Please enter both Student Name and Subject to proceed.")
            st.stop()
            
        if not teacher_file or not student_file:
            st.error("Please upload both files to proceed.")
            st.stop()

        results = []
        total_score = 0
        max_score = 0

        with st.spinner("Step 1/5: Processing uploaded files..."):
            teacher_data = utils.process_uploaded_file(teacher_file, file_purpose="teacher")
            student_images = utils.process_uploaded_file(student_file, file_purpose="student")
            
            if not teacher_data or not student_images:
                st.error("Failed to process one or both files.")
                st.stop()
            
            # Check if teacher file is DOCX (returns tuple) or images (returns list)
            teacher_is_docx = isinstance(teacher_data, tuple) and teacher_data[1] == "docx"
            
            if teacher_is_docx:
                st.success(f"Step 1/5: Files processed (teacher: DOCX, {len(student_images)} student page(s)).")
            else:
                st.success(f"Step 1/5: Files processed ({len(teacher_data)} teacher page(s), {len(student_images)} student page(s)).")

        # --- Step 2: Text Extraction ---
        if teacher_is_docx:
            # Teacher file is DOCX, text already extracted
            with st.spinner("Step 2/5: Loading text from teacher's DOCX file..."):
                teacher_text = teacher_data[0]
                st.success("Step 2/5: Extracted text from DOCX file.")
        else:
            # Teacher file is PDF or image, need OCR
            with st.spinner("Step 2/5: Extracting text from answer key..."):
                teacher_prompt = "Extract all typed text from these images. Maintain the order and structure."
                teacher_text = utils.extract_text_from_images(teacher_data, teacher_prompt)
                st.success("Step 2/5: Extracted text from answer key.")

        with st.spinner("Step 2/5: Extracting handwritten text from student script..."):
            student_prompt = "Transcribe all handwritten text from these images accurately. Preserve any question numbering."
            student_text = utils.extract_text_from_images(student_images, student_prompt)
            st.success("Step 2/5: Extracted handwritten text from student script.")
            
        if not teacher_text or not student_text:
            st.error("Failed to extract text from one or both documents.")
            st.stop()
            
        with st.spinner("Step 3/5: Parsing text into individual answers..."):
            teacher_answers = utils.parse_answers(teacher_text)
            student_answers = utils.parse_answers(student_text)
            st.success("Step 3/5: Answers parsed.")

        with st.spinner("Step 4/5: Comparing answers and generating feedback..."):
            progress_bar = st.progress(0)
            num_questions = len(teacher_answers)
            
            for i, (q_num, t_answer) in enumerate(teacher_answers.items()):
                s_answer = student_answers.get(q_num, "No answer found for this question.")
                
                score_data = utils.get_score_and_feedback(t_answer, s_answer)
                
                score = score_data.get('score', 0)
                feedback = score_data.get('feedback', 'Error.')
                
                results.append({
                    "Question": q_num,
                    "Teacher's Answer": t_answer,
                    "Student's Answer": s_answer,
                    "Score": f"{score}/10",
                    "Feedback": feedback
                })
                
                total_score += score
                max_score += 10
                
                progress_bar.progress((i + 1) / num_questions, text=f"Grading Question {q_num}...")
                time.sleep(0.1)

            progress_bar.empty()
            st.success("Step 4/5: All answers graded!")

        with st.spinner("Step 5/5: Saving results..."):
            final_percentage = (total_score / max_score) * 100 if max_score > 0 else 0
            summary = {
                "total_score": total_score,
                "max_score": max_score,
                "percentage": round(final_percentage, 2)
            }
            
            saved_file = utils.save_results_to_json(student_name, subject, results, summary)
            if saved_file:
                st.success(f"Step 5/5: Results saved successfully to {saved_file}!")
            else:
                st.warning("Step 5/5: Could not save results, but grading is complete.")

        st.balloons()
        st.header("📈 Final Results")
        
        if max_score > 0:
            st.metric(label="Total Score", value=f"{total_score} / {max_score}", delta=f"{final_percentage:.1f}%")
        else:
            st.metric(label="Total Score", value="0 / 0", delta="No questions found to grade.")

        st.subheader("Detailed Breakdown")
        st.data_editor(
            results,
            column_config={
                "Question": st.column_config.TextColumn("Q#", width="small"),
                "Teacher's Answer": st.column_config.TextColumn("Answer Key"),
                "Student's Answer": st.column_config.TextColumn("Student Script"),
                "Score": st.column_config.TextColumn("Score", width="small"),
                "Feedback": st.column_config.TextColumn("AI Feedback", width="large"),
            },
            use_container_width=True,
            hide_index=True,
            height=400,
            key="grading_results_editor"
        )

        with st.expander("Show Raw Extracted Text (for debugging)"):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Teacher's Text (Raw)")
                st.text_area("", teacher_text, height=300, key="raw_teacher")
            with c2:
                st.subheader("Student's Text (Raw)")
                st.text_area("", student_text, height=300, key="raw_student")

with tab2:
    st.header("📊 Student Statistics Dashboard")
    
    all_results = utils.load_all_results()
    
    if not all_results:
        st.warning("No saved results found. Grade some papers first in the 'Grade New Paper' tab!")
    else:
        st.success(f"Found {len(all_results)} saved result(s)")
        
        summary_data = []
        for result in all_results:
            summary_data.append({
                "Student Name": result.get("student_name", "N/A"),
                "Subject": result.get("subject", "N/A"),
                "Score": f"{result['summary']['total_score']}/{result['summary']['max_score']}",
                "Percentage": f"{result['summary']['percentage']}%",
                "Date": result.get("timestamp", "N/A")
            })
        
        df_summary = pd.DataFrame(summary_data)
        
        st.subheader("All Students Summary")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        st.subheader("View Detailed Results")
        
        options = [f"{r['student_name']} - {r['subject']}" for r in all_results]
        selected_option = st.selectbox("Select a student result to view details:", options)
        
        if selected_option:
            selected_index = options.index(selected_option)
            selected_result = all_results[selected_index]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Student", selected_result['student_name'])
            with col2:
                st.metric("Subject", selected_result['subject'])
            with col3:
                st.metric(
                    "Score", 
                    f"{selected_result['summary']['total_score']}/{selected_result['summary']['max_score']}", 
                    delta=f"{selected_result['summary']['percentage']}%"
                )
            
            st.subheader("Question-by-Question Breakdown")
            st.data_editor(
                selected_result['detailed_breakdown'],
                column_config={
                    "Question": st.column_config.TextColumn("Q#", width="small"),
                    "Teacher's Answer": st.column_config.TextColumn("Answer Key"),
                    "Student's Answer": st.column_config.TextColumn("Student Script"),
                    "Score": st.column_config.TextColumn("Score", width="small"),
                    "Feedback": st.column_config.TextColumn("AI Feedback", width="large"),
                },
                use_container_width=True,
                hide_index=True,
                height=400,
                key="statistics_detailed_breakdown_editor"
            )
