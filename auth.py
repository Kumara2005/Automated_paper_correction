import streamlit as st
import sqlite3
import bcrypt
import time

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    with sqlite3.connect('results_db.sqlite') as conn:
        cursor = conn.cursor()
        # Create Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
                subject TEXT
            );
        ''')
        # Create Results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY,
                student_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                teacher_username TEXT NOT NULL,
                total_score INTEGER NOT NULL,
                max_score INTEGER NOT NULL,
                percentage REAL NOT NULL,
                overall_feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_name) REFERENCES users(username),
                FOREIGN KEY(teacher_username) REFERENCES users(username)
            );
        ''')
        # Create Detailed Breakdown table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detailed_results (
                id INTEGER PRIMARY KEY,
                result_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                teacher_answer TEXT NOT NULL,
                student_answer TEXT NOT NULL,
                score_str TEXT NOT NULL,
                feedback TEXT NOT NULL,
                FOREIGN KEY(result_id) REFERENCES results(id)
            );
        ''')
        conn.commit()

def hash_password(password):
    """Hashes a password for storing."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    """Checks a password against a stored hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except Exception:
        return False

def signup(conn):
    """Handles the user signup logic."""
    st.subheader("Create New Account")
    
    role = st.radio("I am a:", ('Student', 'Teacher'))
    subject = st.text_input("Subject (e.g., 'Math', 'History')", key="signup_subject")
    new_username = st.text_input("Username", key="signup_user")
    new_password = st.text_input("Password", type="password", key="signup_pass")
    
    if st.button("Sign Up", use_container_width=True):
        if not (role and subject and new_username and new_password):
            st.error("Please fill out all fields.")
            return

        try:
            hashed_pw = hash_password(new_password)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, subject) VALUES (?, ?, ?, ?)",
                (new_username, hashed_pw, role.lower(), subject)
            )
            conn.commit()
            st.success("Account created successfully! Please log in.")
            time.sleep(1)
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Username already exists. Please choose another one.")
        except Exception as e:
            st.error(f"An error occurred: {e}")

def login(conn):
    """Handles the user login logic."""
    st.subheader("Login to Your Account")
    
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    
    if st.button("Login", type="primary", use_container_width=True):
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, role, subject FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        
        if user_data and check_password(password, user_data[0]):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user_data[1]
            st.session_state.subject = user_data[2]
            st.rerun()
        else:
            st.error("Invalid username or password.")

def render_login_page():
    """Displays the login and signup forms."""
    st.title("🤖 Welcome to the AI Paper Corrector")
    st.write("Please log in or create an account to continue.")
    
    with sqlite3.connect('results_db.sqlite') as conn:
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        
        with login_tab:
            login(conn)
        
        with signup_tab:
            signup(conn)

def handle_logout():
    """Clears session state and logs the user out."""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.subject = None
    st.rerun()
