# app.py
# The Streamlit user interface for StudyMate AI.
# Run with:  streamlit run app.py

from datetime import date, timedelta

import streamlit as st

from agent import run_agent

st.set_page_config(
    page_title="StudyMate AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------------
# STYLING (CSS) - light background, navy and purple accents
# ---------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root { --navy:#1b2559; --purple:#7c5cff; --soft:#f3f1ff; --border:#e5e2f7; }

html, body, .stApp, .stMarkdown, button, input, textarea { font-family:'Inter', sans-serif; }
.stApp { background:#fafaff; }
#MainMenu, footer { visibility:hidden; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:960px; padding-top:2rem; padding-bottom:6rem; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid var(--border); }
.brand { display:flex; align-items:center; gap:12px; margin-bottom:1.2rem; }
.brand-logo { width:44px; height:44px; border-radius:14px; display:flex; align-items:center;
  justify-content:center; font-size:22px; background:linear-gradient(135deg,var(--navy),var(--purple)); }
.brand-name { font-weight:800; font-size:1.2rem; color:var(--navy); line-height:1.1; }
.brand-tag { font-size:.78rem; color:#7b7f9e; }
.side-label { font-size:.72rem; font-weight:700; letter-spacing:.08em; color:#9a9dbb; margin:.6rem 0 .3rem; }

/* Buttons */
.stButton > button { border-radius:14px; border:1px solid var(--border); background:#ffffff;
  color:var(--navy); padding:.65rem 1rem; font-weight:500; transition:all .15s ease; }
.stButton > button div { justify-content:flex-start; text-align:left; }
.stButton > button:hover { border-color:var(--purple); color:var(--purple); background:var(--soft); }
.stDownloadButton > button { border-radius:12px; background:var(--navy); color:#fff; border:none; font-weight:600; }
.stDownloadButton > button:hover { background:var(--purple); color:#fff; }

/* Welcome screen */
.hero { background:linear-gradient(135deg,var(--navy) 0%,#4b3fb3 60%,var(--purple) 100%);
  border-radius:24px; padding:2rem 1.6rem; color:#fff; margin-bottom:1.2rem;
  box-shadow:0 12px 30px rgba(60,50,150,.18); }
.hero-badge { display:inline-block; background:rgba(255,255,255,.18); border-radius:999px;
  padding:.2rem .8rem; font-size:.75rem; font-weight:600; margin-bottom:.8rem; }
.hero h1 { color:#fff; font-size:1.9rem; font-weight:800; margin:0 0 .4rem 0; line-height:1.2; }
.hero p { color:#e5e1ff; margin:0; font-size:1rem; }
.tool-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px; margin-bottom:1.2rem; }
.tool-card { background:#fff; border:1px solid var(--border); border-radius:18px; padding:1rem 1.1rem;
  box-shadow:0 4px 14px rgba(40,40,120,.05); }
.tool-card .icon { font-size:1.5rem; }
.tool-card .name { font-weight:700; color:var(--navy); margin-top:.2rem; }
.tool-card .desc { font-size:.85rem; color:#6f7396; }
.section-title { font-weight:700; color:var(--navy); margin:.4rem 0 .6rem; font-size:1.05rem; }

/* Chat */
[data-testid="stChatMessage"] { background:#ffffff; border:1px solid var(--border); border-radius:18px;
  padding:1rem 1.1rem; margin-bottom:.8rem; box-shadow:0 3px 12px rgba(40,40,120,.04); }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:var(--soft); }
[data-testid="stChatInput"] { border-radius:18px; border:1px solid var(--border); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------
# DATA: example prompts, tool shortcuts, tool names
# ---------------------------------------------------------------
exam_date_text = (date.today() + timedelta(days=21)).strftime("%d %B %Y")

TOOL_SHORTCUTS = [
    ("📘 Topic Explainer", "Explain photosynthesis in simple words with an example"),
    ("📝 Quiz Generator", "Give me a medium difficulty quiz with 5 questions on Python loops"),
    ("✅ Quiz Evaluator", "How do I submit my quiz answers for checking?"),
    ("🗒️ Study Notes", "Make short revision notes on the French Revolution"),
    ("📅 Study Planner", f"Make a study plan for Maths and Physics, 3 hours per day, exam on {exam_date_text}"),
    ("🧮 Calculator", "Calculate (25 * 4 + 18) / 3"),
]

EXAMPLE_PROMPTS = [
    "Explain recursion simply, then give me a 3 question easy quiz on it",
    "Make detailed study notes on the water cycle",
    f"Plan my study: Chemistry, Biology, 2.5 hours daily, exam on {exam_date_text}",
    "What is 15% of 2,400 plus 350?",
]

TOOL_LABELS = {
    "explain_topic": "Topic Explainer",
    "generate_quiz": "Quiz Generator",
    "evaluate_quiz": "Quiz Evaluator",
    "generate_study_notes": "Study Notes Generator",
    "create_study_plan": "Study Planner",
    "calculate": "Calculator",
}

# ---------------------------------------------------------------
# SESSION STATE (memory for this browser session)
# ---------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# ---------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-logo">🎓</div><div>'
        '<div class="brand-name">StudyMate AI</div>'
        '<div class="brand-tag">Your AI study agent</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-label">TOOLS</div>', unsafe_allow_html=True)
    for index, (label, example) in enumerate(TOOL_SHORTCUTS):
        if st.button(label, key=f"shortcut_{index}", use_container_width=True):
            st.session_state.pending_prompt = example
    st.markdown('<div class="side-label">CHAT</div>', unsafe_allow_html=True)
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()
    st.caption("Powered by Google Gemini")

# ---------------------------------------------------------------
# GET THE NEW PROMPT (typed, or from a button)
# ---------------------------------------------------------------
typed_prompt = st.chat_input("Ask StudyMate: explain, quiz, notes, plan or calculate...")
prompt = typed_prompt or st.session_state.pending_prompt
st.session_state.pending_prompt = None

# ---------------------------------------------------------------
# WELCOME SCREEN (only before the first message)
# ---------------------------------------------------------------
if not st.session_state.messages and not prompt:
    st.markdown(
        '<div class="hero"><div class="hero-badge">✨ AI Study Agent</div>'
        '<h1>Study smarter with StudyMate AI</h1>'
        '<p>Ask me to explain a topic, quiz you, make notes, plan your exams '
        'or solve calculations. I pick the right tool for you.</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tool-grid">'
        '<div class="tool-card"><div class="icon">📘</div><div class="name">Topic Explainer</div>'
        '<div class="desc">Simple explanations with examples</div></div>'
        '<div class="tool-card"><div class="icon">📝</div><div class="name">Quiz Generator</div>'
        '<div class="desc">Practice questions at any difficulty</div></div>'
        '<div class="tool-card"><div class="icon">✅</div><div class="name">Quiz Evaluator</div>'
        '<div class="desc">Marks and feedback on your answers</div></div>'
        '<div class="tool-card"><div class="icon">🗒️</div><div class="name">Study Notes</div>'
        '<div class="desc">Revision notes you can download</div></div>'
        '<div class="tool-card"><div class="icon">📅</div><div class="name">Study Planner</div>'
        '<div class="desc">A timetable up to your exam date</div></div>'
        '<div class="tool-card"><div class="icon">🧮</div><div class="name">Calculator</div>'
        '<div class="desc">Fast and accurate maths</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-title">Try an example</div>', unsafe_allow_html=True)
    columns = st.columns(2)
    for index, example in enumerate(EXAMPLE_PROMPTS):
        with columns[index % 2]:
            if st.button(example, key=f"example_{index}", use_container_width=True):
                st.session_state.pending_prompt = example
                st.rerun()

# ---------------------------------------------------------------
# SHOW OLD MESSAGES
# ---------------------------------------------------------------
for index, message in enumerate(st.session_state.messages):
    avatar = "🧑‍🎓" if message["role"] == "user" else "🎓"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("tools_used"):
            names = [TOOL_LABELS.get(tool, tool) for tool in message["tools_used"]]
            st.caption("🛠️ Tool used: " + ", ".join(names))
        if message.get("notes"):
            st.download_button(
                "⬇️ Download notes (.txt)",
                data=message["notes"],
                file_name="studymate_notes.txt",
                mime="text/plain",
                key=f"download_{index}",
            )

# ---------------------------------------------------------------
# HANDLE A NEW MESSAGE
# ---------------------------------------------------------------
if prompt:
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("StudyMate is thinking..."):
            result = run_agent(prompt, list(st.session_state.messages))

    # Save both messages, then redraw the page
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["text"],
        "tools_used": result["tools_used"],
        "notes": result["notes"],
    })
    st.rerun()
