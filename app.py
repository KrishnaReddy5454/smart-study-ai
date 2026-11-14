import socket

old_getaddrinfo = socket.getaddrinfo


def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]


socket.getaddrinfo = new_getaddrinfo

from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

from database import (
    authenticate_user,
    get_user_sessions,
    init_db,
    load_session_by_id,
    register_user,
    save_study_session,
    update_session_chat,
)
from styles import apply_custom_styles, DEMO_DOCUMENT_TEXT
from utils import (
    PreparedTextResult,
    StudyKit,
    ask_study_assistant,
    extract_and_prepare_text,
    generate_markdown_study_kit,
    generate_quiz_by_difficulty,
    generate_study_materials,
    generate_text_study_kit,
)

# Load environment variables and initialize database
load_dotenv()
init_db()

st.set_page_config(
    page_title="SmartStudy AI - University Exam Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject modern SaaS styling
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
apply_custom_styles(dark_mode=st.session_state.get("dark_mode", False))

# Initialize authentication and app state in session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "current_session_id" not in st.session_state:
    st.session_state["current_session_id"] = None
if "active_session_title" not in st.session_state:
    st.session_state["active_session_title"] = None
if "extracted_result" not in st.session_state:
    st.session_state["extracted_result"] = None
if "current_file_signatures" not in st.session_state:
    st.session_state["current_file_signatures"] = []
if "study_kit" not in st.session_state:
    st.session_state["study_kit"] = None
if "quiz_submitted" not in st.session_state:
    st.session_state["quiz_submitted"] = False
if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = {}
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []


# ==========================================
# 1. Authentication View (When not logged in)
# ==========================================
if not st.session_state["logged_in"]:
    _, auth_col, _ = st.columns([1, 2, 1])
    with auth_col:
        st.markdown(
            """
            <div class="auth-header">
                <h1>📚 SmartStudy AI</h1>
                <p>Your intelligent educational platform for university exam mastery</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_signup = st.tabs(["🔑 Log In", "📝 Create Account"])

        # Login Tab
        with tab_login:
            st.subheader("Account Login")
            with st.form("login_form"):
                username_input = st.text_input("Username", key="login_username_input").strip()
                password_input = st.text_input("Password", type="password", key="login_password_input")
                login_btn = st.form_submit_button("Log In", type="primary", use_container_width=True)

                if login_btn:
                    if not username_input or not password_input:
                        st.warning("Please enter both username and password.")
                    else:
                        user = authenticate_user(username_input, password_input)
                        if user:
                            st.session_state["logged_in"] = True
                            st.session_state["user"] = user
                            st.success(f"Welcome back, {user['full_name']}!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password. Please try again.")

        # Sign Up Tab
        with tab_signup:
            st.subheader("Register New Account")
            with st.form("signup_form"):
                new_full_name = st.text_input("Full Name", key="signup_name_input").strip()
                new_username = st.text_input("Choose Username", key="signup_user_input").strip()
                new_password = st.text_input("Choose Password (min 4 chars)", type="password", key="signup_pass_input")
                confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_input")
                signup_btn = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if signup_btn:
                    if not new_full_name or not new_username or not new_password:
                        st.warning("All fields are required.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_user(new_full_name, new_username, new_password)
                        if ok:
                            st.success(f"{msg} You may now switch to the 'Log In' tab to access your account.")
                        else:
                            st.error(msg)

    st.stop()


# ==========================================
# 2. Authenticated Workspace
# ==========================================
user = st.session_state["user"]
user_sessions = get_user_sessions(user["id"])
session_count = len(user_sessions)

# --- Sidebar: User Info, Logout & Session History ---
with st.sidebar:
    st.markdown(f"### 👤 {user['full_name']}")
    st.caption(f"Signed in as **@{user['username']}**")

    if st.button("🚪 Log Out", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    # Dark Mode toggle
    dark_mode_on = st.toggle(
        "🌙 Dark Mode",
        value=st.session_state.get("dark_mode", False),
        key="dark_mode_toggle",
    )
    if dark_mode_on != st.session_state.get("dark_mode", False):
        st.session_state["dark_mode"] = dark_mode_on
        st.rerun()

    st.divider()

    # Button to start fresh session
    if st.button("➕ Start New Session", use_container_width=True, type="secondary"):
        st.session_state["current_session_id"] = None
        st.session_state["active_session_title"] = None
        st.session_state["extracted_result"] = None
        st.session_state["study_kit"] = None
        st.session_state["chat_messages"] = []
        st.session_state["quiz_submitted"] = False
        st.session_state["user_answers"] = {}
        st.session_state["current_file_signatures"] = []
        st.rerun()

    st.subheader("📚 Past Study Sessions")

    if not user_sessions:
        st.caption("No saved sessions yet. Upload PDFs and generate a study kit to save your first session!")
    else:
        for sess in user_sessions:
            is_active = (st.session_state.get("current_session_id") == sess["id"])
            icon = "🟢" if is_active else "📖"
            btn_title = f"{icon} {sess['title']}"

            if st.button(
                btn_title,
                key=f"load_session_{sess['id']}",
                use_container_width=True,
                help=f"Created: {sess['created_at']}",
            ):
                session_data = load_session_by_id(sess["id"])
                if session_data:
                    st.session_state["current_session_id"] = session_data["id"]
                    st.session_state["active_session_title"] = session_data["title"]

                    doc_text = session_data.get("document_text", "")
                    st.session_state["extracted_result"] = PreparedTextResult(
                        text=doc_text,
                        was_truncated=False,
                        total_pages=1,
                        total_chars=len(doc_text),
                        file_count=1,
                    )

                    if session_data.get("study_kit"):
                        try:
                            st.session_state["study_kit"] = StudyKit.model_validate(session_data["study_kit"])
                        except Exception:
                            st.session_state["study_kit"] = None
                    else:
                        st.session_state["study_kit"] = None

                    st.session_state["chat_messages"] = session_data.get("chat_history", [])
                    st.session_state["quiz_submitted"] = False
                    st.session_state["user_answers"] = {}
                    st.session_state["current_file_signatures"] = []
                    st.rerun()


# --- Main Application: Top Welcome Hero Banner ---
st.markdown(
    f"""
    <div class="welcome-hero">
        <div>
            <h2>👋 Welcome back, {user['full_name']}!</h2>
            <p>Upload lecture slides or textbook chapters to generate summaries, flashcards, quizzes, and consult your AI Tutor.</p>
        </div>
        <div class="welcome-stats-badge">
            📚 {session_count} Saved Session{'s' if session_count != 1 else ''}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Banner if a past session is loaded
if st.session_state.get("active_session_title"):
    active_col, clear_col = st.columns([4, 1])
    with active_col:
        st.info(f"📂 Currently Viewing Saved Session: **{st.session_state['active_session_title']}**")
    with clear_col:
        if st.button("Close Session", use_container_width=True):
            st.session_state["current_session_id"] = None
            st.session_state["active_session_title"] = None
            st.session_state["extracted_result"] = None
            st.session_state["study_kit"] = None
            st.session_state["chat_messages"] = []
            st.rerun()

# Demo Mode: One-click load of built-in OS/Deadlocks notes
demo_col, _ = st.columns([1, 2])
with demo_col:
    if st.button(
        "⚡ Load Sample CSE Notes (Demo)",
        use_container_width=True,
        help="Loads built-in OS/Deadlocks/Banker's Algorithm notes so you can test the app without uploading a PDF.",
    ):
        demo_result = PreparedTextResult(
            text=DEMO_DOCUMENT_TEXT,
            was_truncated=False,
            total_pages=4,
            total_chars=len(DEMO_DOCUMENT_TEXT),
            file_count=1,
        )
        st.session_state["extracted_result"] = demo_result
        st.session_state["current_file_signatures"] = [("Demo_OS_Notes.pdf", len(DEMO_DOCUMENT_TEXT))]
        st.session_state["study_kit"] = None
        st.session_state["quiz_submitted"] = False
        st.session_state["user_answers"] = {}
        st.session_state["chat_messages"] = []
        st.session_state["current_session_id"] = None
        st.session_state["active_session_title"] = None
        st.rerun()

# Multi-file Uploader Widget
uploaded_files = st.file_uploader(
    label="Upload Study PDFs (Up to 5 files)",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select up to 5 PDF files (lecture slides, notes, or textbook chapters).",
)

# Handle file uploads
if uploaded_files:
    if len(uploaded_files) > 5:
        st.warning("⚠️ Please upload up to 5 PDF files at once.")
        st.session_state["extracted_result"] = None
        st.session_state["current_file_signatures"] = []
        st.session_state["study_kit"] = None
        st.session_state["chat_messages"] = []
    else:
        current_signatures = [(f.name, getattr(f, "size", 0)) for f in uploaded_files]
        if st.session_state["current_file_signatures"] != current_signatures:
            try:
                with st.spinner("Extracting and preparing text across documents..."):
                    result = extract_and_prepare_text(uploaded_files)
                    st.session_state["extracted_result"] = result
                    st.session_state["current_file_signatures"] = current_signatures
                    st.session_state["study_kit"] = None
                    st.session_state["quiz_submitted"] = False
                    st.session_state["user_answers"] = {}
                    st.session_state["chat_messages"] = []
                    st.session_state["current_session_id"] = None
                    st.session_state["active_session_title"] = None
            except ValueError as e:
                st.error(f"Error reading uploaded PDFs: {e}")
                st.session_state["extracted_result"] = None
                st.session_state["current_file_signatures"] = []
                st.session_state["chat_messages"] = []

# Display extraction summary and action controls when files are processed
if st.session_state.get("extracted_result") is not None:
    res = st.session_state["extracted_result"]

    # Clean metric summary with hover lift styling
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("📁 Files / Docs", f"{res.file_count}")
    with m2:
        st.metric("📄 Total Pages", f"{res.total_pages:,}")
    with m3:
        st.metric("🔤 Total Characters", f"{res.total_chars:,}")
    with m4:
        st.metric("🛡️ Token Safety", "Condensed" if res.was_truncated else "Full Text")

    if res.was_truncated:
        st.info(
            "ℹ️ The combined text was automatically condensed across all uploaded documents "
            "to stay within safe AI token limits while preserving balanced context."
        )

    with st.expander("🔍 Preview Document Text (First 500 Characters)", expanded=False):
        preview_text = res.text[:500] + ("..." if len(res.text) > 500 else "")
        st.text_area(
            label="Combined Text Preview",
            value=preview_text,
            height=150,
            disabled=True,
        )

    # Action Button to generate study kit (only shown if kit not already generated)
    st.write("---")
    if st.session_state.get("study_kit") is None:
        btn_col, _ = st.columns([1, 2])
        with btn_col:
            generate_clicked = st.button(
                "🚀 Generate Study Kit",
                type="primary",
                use_container_width=True,
            )

        if generate_clicked:
            try:
                with st.spinner("Analyzing combined documents and generating study materials with Gemini..."):
                    study_kit = generate_study_materials(res.text)
                    st.session_state["study_kit"] = study_kit
                    st.session_state["quiz_submitted"] = False
                    st.session_state["user_answers"] = {}

                    # Automatically save session to SQLite
                    filenames_str = (
                        ", ".join([sig[0] for sig in st.session_state["current_file_signatures"]])
                        if st.session_state["current_file_signatures"]
                        else "Study Document"
                    )
                    timestamp_str = datetime.now().strftime("%b %d, %I:%M %p")
                    session_title = f"{filenames_str} ({timestamp_str})"

                    new_sess_id = save_study_session(
                        user_id=user["id"],
                        title=session_title,
                        document_text=res.text,
                        study_kit_data=study_kit,
                    )
                    st.session_state["current_session_id"] = new_sess_id
                    st.session_state["active_session_title"] = session_title
                    st.success(f"Study kit generated and saved to your history as **{session_title}**!")
                    st.rerun()

            except ValueError as e:
                st.error(f"Generation Notice: {e}")
            except Exception as e:
                st.error(f"Unexpected Error: {e}")

    # Tabs for Summary, Flashcards, Quiz, and Ask Your Notes (AI Tutor)
    tab_summary, tab_flashcards, tab_quiz, tab_chat = st.tabs([
        "📋 Summary",
        "🗂️ Flashcards",
        "❓ Practice Quiz",
        "💬 Ask Your Notes",
    ])

    # Tab 1: Summary
    with tab_summary:
        if st.session_state.get("study_kit") is not None:
            kit = st.session_state["study_kit"]
            st.subheader("📌 5-Bullet Key Summary")
            st.caption("High-yield conceptual takeaways from your study materials:")

            for idx, bullet in enumerate(kit.summary, start=1):
                st.markdown(
                    f'<div class="summary-card"><strong>{idx}.</strong> {bullet}</div>',
                    unsafe_allow_html=True,
                )

            st.write("")
            # Download Study Kit (.txt) button
            txt_content = generate_text_study_kit(
                st.session_state.get("active_session_title") or "Study Kit",
                kit,
            )
            st.download_button(
                label="⬇️ Download Study Kit (.txt)",
                data=txt_content,
                file_name=f"Study_Kit_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
                help="Export summary, flashcards, and quiz as a clean printable text (.txt) study sheet.",
            )
        else:
            st.info("💡 Click **'🚀 Generate Study Kit'** above to generate summary bullets, flashcards, and the quiz.")

    # Tab 2: Flashcards
    with tab_flashcards:
        if st.session_state.get("study_kit") is not None:
            kit = st.session_state["study_kit"]
            st.subheader("💡 Study Flashcards (6 Cards)")
            st.caption("Click to expand each card and check your knowledge.")

            cards_col1, cards_col2 = st.columns(2)
            for idx, card in enumerate(kit.flashcards, start=1):
                target_col = cards_col1 if idx % 2 != 0 else cards_col2
                with target_col:
                    with st.container(border=True):
                        st.markdown(f"**Card {idx}**")
                        st.markdown(f"**Q:** {card.question}")
                        with st.expander(f"👀 Show Answer #{idx}"):
                            st.markdown(f"**A:** {card.answer}")
        else:
            st.info("💡 Click **'🚀 Generate Study Kit'** above to generate summary bullets, flashcards, and the quiz.")

    # Tab 3: Practice Quiz
    with tab_quiz:
        if st.session_state.get("study_kit") is not None:
            kit = st.session_state["study_kit"]
            st.subheader("📝 Practice Quiz (5 Questions)")
            st.caption("Select your answers below and click **Submit Quiz** to check your score.")

            # Difficulty selector and Fresh Quiz regeneration
            diff_col, regen_col = st.columns([2, 1])
            with diff_col:
                quiz_difficulty = st.selectbox(
                    "🎯 Quiz Difficulty Level:",
                    options=["Easy", "Medium", "Hard"],
                    index=1,
                    key="quiz_difficulty_selector",
                    help="Easy: recall questions. Medium: applied reasoning. Hard: analytical/edge-case questions.",
                )
            with regen_col:
                st.write("")
                if st.button(
                    "🔄 Generate Fresh Quiz",
                    use_container_width=True,
                    type="secondary",
                    key="regen_quiz_btn",
                ):
                    try:
                        with st.spinner(f"Generating a fresh **{quiz_difficulty}** quiz with Gemini..."):
                            new_quiz = generate_quiz_by_difficulty(res.text, quiz_difficulty)
                            current_kit = st.session_state["study_kit"]
                            if current_kit:
                                updated_kit = StudyKit(
                                    summary=current_kit.summary,
                                    flashcards=current_kit.flashcards,
                                    quiz=new_quiz,
                                )
                                st.session_state["study_kit"] = updated_kit
                                st.session_state["quiz_submitted"] = False
                                st.session_state["user_answers"] = {}
                                st.success(f"✅ Fresh **{quiz_difficulty}** quiz generated!")
                                st.rerun()
                    except ValueError as e:
                        st.error(f"Quiz generation error: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error during quiz regeneration: {e}")

            with st.form("multi_pdf_quiz_form"):
                selected_answers = {}
                for idx, q in enumerate(kit.quiz, start=1):
                    st.markdown(f"**Question {idx}:** {q.question}")
                    selected_answers[idx] = st.radio(
                        label=f"Options for Question {idx}",
                        options=q.options,
                        index=None,
                        key=f"q_choice_{idx}",
                        label_visibility="collapsed",
                    )
                    if idx < len(kit.quiz):
                        st.divider()

                submit_quiz = st.form_submit_button("Submit Quiz", type="primary", use_container_width=True)
                if submit_quiz:
                    st.session_state["quiz_submitted"] = True
                    st.session_state["user_answers"] = selected_answers

            # Quiz Results & Explanations (Professional Academic Review)
            if st.session_state.get("quiz_submitted"):
                user_answers = st.session_state.get("user_answers", {})
                total_questions = len(kit.quiz)
                correct_count = 0

                for idx, q in enumerate(kit.quiz, start=1):
                    if user_answers.get(idx) == q.correct_answer:
                        correct_count += 1

                percentage = (correct_count / total_questions) * 100

                # Determine academic performance status
                if percentage >= 80:
                    status_label = "Excellent Mastery"
                    status_color = "#10B981"
                    status_desc = "Demonstrated strong grasp of core concepts. Well-prepared for exam questions on this material."
                elif percentage >= 50:
                    status_label = "Good Progress"
                    status_color = "#F59E0B"
                    status_desc = "Satisfactory baseline knowledge. Review incorrect items below to address specific conceptual gaps."
                else:
                    status_label = "Needs Revision"
                    status_color = "#EF4444"
                    status_desc = "Significant conceptual gaps detected. Thorough revision of the summary and flashcards is strongly recommended."

                st.write("---")
                st.markdown("### 📊 Academic Assessment & Performance Summary")

                # Clean professional score summary card
                col_score, col_pct, col_status = st.columns([1, 1, 2])
                with col_score:
                    st.metric("Total Score", f"{correct_count} / {total_questions}")
                with col_pct:
                    st.metric("Percentage", f"{percentage:.0f}%")
                with col_status:
                    st.markdown(
                        f"""
                        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 4px solid {status_color}; border-radius: 10px; padding: 12px 18px; margin-top: 4px;">
                            <div style="font-size: 0.82rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em;">Academic Performance Status</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: {status_color}; margin: 2px 0;">{status_label}</div>
                            <div style="font-size: 0.88rem; color: #475569; line-height: 1.4;">{status_desc}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.write("")
                st.subheader("Question-by-Question Review & Explanations")
                for idx, q in enumerate(kit.quiz, start=1):
                    chosen = user_answers.get(idx)
                    is_correct = chosen == q.correct_answer
                    if is_correct:
                        st.success(f"✅ **Question {idx}:** {q.question}\n\n**Your Answer:** {chosen} (Correct)")
                    else:
                        st.error(
                            f"❌ **Question {idx}:** {q.question}\n\n"
                            f"**Your Answer:** {chosen or 'No answer selected'}\n\n"
                            f"**Correct Answer:** {q.correct_answer}"
                        )
                    with st.expander(f"💡 Explanation for Question {idx}", expanded=True):
                        st.markdown(q.explanation)
        else:
            st.info("💡 Click **'🚀 Generate Study Kit'** above to generate summary bullets, flashcards, and the quiz.")

    # Tab 4: Ask Your Notes (AI Tutor)
    with tab_chat:
        st.subheader("💬 Ask Your Notes (AI Exam Tutor)")
        st.caption(
            "Your dynamic university tutor. Ask any question from your notes and receive answers "
            "formatted specifically for university exams (2-Mark, 5-Mark, 10-Mark, or Simple EL5)."
        )

        # Controls: Format selector and Clear Chat button
        ctrl_col1, ctrl_col2 = st.columns([3, 1])
        with ctrl_col1:
            selected_format = st.selectbox(
                "🎯 Select Exam Answer Format:",
                options=[
                    "2-Mark Answer (Crisp & Direct)",
                    "5-Mark Answer (Structured)",
                    "10-Mark Answer (Detailed Essay)",
                    "Simple Explanation (EL5)",
                ],
                index=0,
                help="Choose how the AI Tutor formats your answer to match university exam question scoring.",
                key="answer_format_choice",
            )
        with ctrl_col2:
            st.write("")
            st.write("")
            if st.button("🗑️ Clear Chat", use_container_width=True, key="clear_chat_button"):
                st.session_state["chat_messages"] = []
                if st.session_state.get("current_session_id"):
                    update_session_chat(st.session_state["current_session_id"], [])
                st.rerun()

        st.divider()

        # Display conversation history
        if not st.session_state["chat_messages"]:
            st.info(
                "👋 Hello! Ask me any question from your uploaded study materials. "
                "I will structure the answer according to the selected format above."
            )
        else:
            for msg in st.session_state["chat_messages"]:
                with st.chat_message(msg["role"]):
                    if msg.get("role") == "assistant" and msg.get("format"):
                        st.caption(f"🎯 Format: {msg['format']}")
                    st.markdown(msg["content"])

        # One-click Helper Button for Question Paper Solving
        solve_paper_prompt = (
            "Identify all the questions listed in the uploaded question paper/document "
            "and provide complete, exam-ready answers for every single one using the uploaded study notes."
        )
        solve_btn_clicked = st.button(
            "📝 Solve All Questions from Uploaded Question Paper",
            type="secondary",
            use_container_width=True,
            help="Automatically identifies all questions in your question paper document and solves each using your uploaded study notes.",
        )

        user_query = st.chat_input("Ask any question from your uploaded PDFs...")

        active_query = None
        if solve_btn_clicked:
            active_query = solve_paper_prompt
        elif user_query:
            active_query = user_query

        if active_query:
            # 1. Append user question to history
            st.session_state["chat_messages"].append({
                "role": "user",
                "content": active_query,
            })
            with st.chat_message("user"):
                st.markdown(active_query)

            # 2. Generate and display AI Tutor response
            with st.chat_message("assistant"):
                with st.spinner("AI Tutor is formulating your exam response..."):
                    try:
                        tutor_response = ask_study_assistant(
                            question=active_query,
                            document_text=res.text,
                            answer_format=selected_format,
                            chat_history=st.session_state["chat_messages"][:-1],
                        )
                        st.caption(f"🎯 Format: {selected_format}")
                        st.markdown(tutor_response)
                        st.session_state["chat_messages"].append({
                            "role": "assistant",
                            "content": tutor_response,
                            "format": selected_format,
                        })

                        # Auto-save chat messages to SQLite session if active
                        if st.session_state.get("current_session_id"):
                            update_session_chat(
                                st.session_state["current_session_id"],
                                st.session_state["chat_messages"],
                            )
                        else:
                            timestamp_str = datetime.now().strftime("%b %d, %I:%M %p")
                            chat_sess_title = f"Chat Session ({timestamp_str})"
                            new_sess_id = save_study_session(
                                user_id=user["id"],
                                title=chat_sess_title,
                                document_text=res.text,
                                study_kit_data=st.session_state.get("study_kit") or {},
                            )
                            st.session_state["current_session_id"] = new_sess_id
                            st.session_state["active_session_title"] = chat_sess_title
                            update_session_chat(new_sess_id, st.session_state["chat_messages"])

                    except ValueError as e:
                        err_msg = f"Notice: {e}"
                        st.warning(err_msg)
                        st.session_state["chat_messages"].append({
                            "role": "assistant",
                            "content": err_msg,
                        })
                    except Exception as e:
                        err_msg = f"Unexpected error: {e}"
                        st.error(err_msg)
                        st.session_state["chat_messages"].append({
                            "role": "assistant",
                            "content": err_msg,
                        })
