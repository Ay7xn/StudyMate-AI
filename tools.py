# tools.py
# This file contains:
#   1. Helper functions to talk to Google Gemini
#   2. The 6 tools (normal Python functions) the AI agent can use
#   3. TOOL_DECLARATIONS: descriptions that tell Gemini what each tool does
#   4. run_tool(): runs a tool by its name

import ast
import json
import operator
import os
from datetime import date, datetime

from google import genai
from google.genai import types

# ---------------------------------------------------------------
# PART 1: GEMINI HELPERS
# ---------------------------------------------------------------

# Models are tried in this order. If one is not available or its free
# limit is finished, the next one is tried automatically.
# You can also set your own model with GEMINI_MODEL in secrets.
MODEL_NAMES = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]

# Remembers which model worked last, so we try it first next time.
working_model = None


def get_setting(name):
    """Read a setting from environment variables or Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        # No secrets file found
        return None


def get_client():
    """Create a Gemini client using the API key (never hardcoded)."""
    api_key = get_setting("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Add GEMINI_API_KEY to your Streamlit "
            "secrets (see README.md)."
        )
    return genai.Client(api_key=api_key)


def get_model_names():
    """Return the list of models to try."""
    custom_model = get_setting("GEMINI_MODEL")
    if custom_model:
        return [custom_model] + MODEL_NAMES
    return MODEL_NAMES


def find_available_models(client):
    """Ask Google which text models this API key can actually use."""
    skip_words = ("image", "tts", "live", "audio", "embedding", "robotics", "computer")
    found = []
    try:
        for model in client.models.list():
            name = (model.name or "").replace("models/", "")
            actions = getattr(model, "supported_actions", None) or []
            if ("generateContent" in actions and "flash" in name
                    and not any(word in name for word in skip_words)):
                found.append(name)
    except Exception:
        pass
    return found


def call_gemini(contents, config=None):
    """Send a request to Gemini. Tries other models if one is unavailable."""
    global working_model
    client = get_client()

    names = list(get_model_names())
    if working_model in names:
        names.remove(working_model)
        names.insert(0, working_model)

    last_error = None
    tried = []
    discovered = False
    index = 0
    while index < len(names):
        name = names[index]
        index += 1
        tried.append(name)
        try:
            response = client.models.generate_content(
                model=name, contents=contents, config=config
            )
            working_model = name
            return response
        except Exception as error:
            last_error = error
            text = str(error)
            # Model missing, limit reached or server busy -> try next model
            retry_codes = ("404", "NOT_FOUND", "429", "RESOURCE_EXHAUSTED",
                           "503", "UNAVAILABLE")
            if not any(code in text for code in retry_codes):
                raise
        # When our own list is used up, ask Google which models exist
        if index >= len(names) and not discovered:
            discovered = True
            for new_name in find_available_models(client):
                if new_name not in tried:
                    names.append(new_name)
    raise last_error


def get_response_text(response):
    """Safely get the text from a Gemini response."""
    if not response.candidates:
        return ""
    content = response.candidates[0].content
    if content is None or not content.parts:
        return ""
    return "".join(
        part.text for part in content.parts
        if part.text and not getattr(part, "thought", False)
    )


def ask_gemini(prompt, want_json=False):
    """Simple helper: send one prompt, get the answer text back."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if want_json else None
    )
    response = call_gemini(prompt, config)
    text = get_response_text(response).strip()
    if not text:
        raise ValueError("Gemini gave an empty answer. Please rephrase and try again.")
    return text


def friendly_error(error):
    """Turn technical API errors into simple messages for the student."""
    if isinstance(error, ValueError):
        return str(error)
    text = str(error)
    lower = text.lower()
    if ("api key" in lower or "api_key" in lower or "401" in text
            or "403" in text or "permission_denied" in lower):
        return ("The Gemini API key is missing or not valid. "
                "Please check your secrets settings.")
    if "429" in text or "resource_exhausted" in lower or "quota" in lower:
        return ("The free Gemini limit has been reached for now. "
                "Please wait a minute or two and try again.")
    if "404" in text or "not_found" in lower:
        return ("The Gemini model is not available. Try setting GEMINI_MODEL "
                "in your secrets to a model shown in Google AI Studio. "
                "Details: " + text[:150])
    if "503" in text or "unavailable" in lower or "overloaded" in lower:
        return "Gemini is busy right now. Please try again in a moment."
    if "timeout" in lower or "connection" in lower:
        return "Network problem. Please check your internet and try again."
    return "Something went wrong: " + text[:200]


# ---------------------------------------------------------------
# PART 2: THE SIX TOOLS
# ---------------------------------------------------------------

def explain_topic(topic, level="beginner"):
    """Tool 1: Explain a topic in simple language with examples."""
    if not topic or not str(topic).strip():
        return "Error: please tell me which topic to explain."
    prompt = (
        f"Explain the topic '{topic}' to a {level}-level student in simple "
        "language.\nInclude:\n"
        "1. A short introduction (2-3 sentences)\n"
        "2. The key ideas as bullet points\n"
        "3. One or two easy real-life examples\n"
        "4. A one-line summary\n"
        "Avoid difficult jargon. Use markdown formatting."
    )
    return ask_gemini(prompt)


def generate_quiz(topic, difficulty="medium", num_questions=5):
    """Tool 2: Generate multiple-choice questions (without answers)."""
    if not topic or not str(topic).strip():
        return "Error: please tell me the topic for the quiz."

    # Check the inputs
    difficulty = str(difficulty).lower().strip()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    try:
        num_questions = int(float(num_questions))
    except (ValueError, TypeError):
        num_questions = 5
    num_questions = max(1, min(num_questions, 15))  # keep between 1 and 15

    prompt = (
        f"Create {num_questions} multiple-choice questions on '{topic}' at "
        f"{difficulty} difficulty for a student.\n"
        "Rules:\n"
        "- Number the questions 1, 2, 3...\n"
        "- Give 4 options labelled A, B, C, D for each question\n"
        "- Only ONE option must be correct\n"
        "- DO NOT include the answers or hints anywhere\n"
        "- Put each option on a new line"
    )
    quiz = ask_gemini(prompt)
    return f"Quiz on {topic} ({difficulty}, {num_questions} questions)\n\n{quiz}"


def evaluate_quiz(quiz_questions, student_answers):
    """Tool 3: Check answers, calculate marks (in Python) and give feedback."""
    if not quiz_questions or not str(quiz_questions).strip():
        return "Error: I need the quiz questions to check the answers."
    if not student_answers or not str(student_answers).strip():
        return "Error: please send your answers first, like: 1-A, 2-C, 3-B"

    prompt = (
        "You are a fair examiner. Below are multiple-choice questions and a "
        "student's answers.\nFor EACH question, work out the correct option "
        "and compare it with the student's answer. The student may write "
        "answers like 'A', '1-A', '1) a' or the full option text. If the "
        "student did not answer a question, treat it as wrong.\n\n"
        f"QUESTIONS:\n{quiz_questions}\n\n"
        f"STUDENT ANSWERS:\n{student_answers}\n\n"
        "Reply ONLY with JSON in exactly this format:\n"
        '{"results": [{"question_number": 1, "student_answer": "B", '
        '"correct_answer": "C", "is_correct": false, '
        '"feedback": "one or two sentence explanation"}]}'
    )
    raw_text = ask_gemini(prompt, want_json=True)

    # Clean the text in case Gemini added ```json fences
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    try:
        results = json.loads(raw_text)["results"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return "Error: I could not read the evaluation result. Please try again."

    # The marks are calculated here with normal Python (not by the AI)
    total_questions = len(results)
    if total_questions == 0:
        return "Error: no questions were evaluated. Please try again."
    correct_count = sum(1 for item in results if item.get("is_correct") is True)
    percentage = round(correct_count / total_questions * 100)

    if percentage >= 80:
        remark = "Excellent work!"
    elif percentage >= 50:
        remark = "Good effort, a little more revision will help."
    else:
        remark = "Keep practising, you will improve."

    lines = [f"Score: {correct_count}/{total_questions} ({percentage}%) - {remark}", ""]
    for item in results:
        number = item.get("question_number", "?")
        if item.get("is_correct") is True:
            lines.append(f"Q{number}: Correct. {item.get('feedback', '')}")
        else:
            lines.append(
                f"Q{number}: Wrong. Your answer: {item.get('student_answer', '-')}. "
                f"Correct answer: {item.get('correct_answer', '-')}. "
                f"{item.get('feedback', '')}"
            )
    return "\n".join(lines)


def generate_study_notes(topic, detail_level="standard"):
    """Tool 4: Create revision notes (the app lets the student download them)."""
    if not topic or not str(topic).strip():
        return "Error: please tell me the topic for the notes."
    detail_level = str(detail_level).lower().strip()
    if detail_level not in ("short", "standard", "detailed"):
        detail_level = "standard"

    prompt = (
        f"Write {detail_level} revision notes on '{topic}' for a student.\n"
        "Format:\n"
        "- Start with the title in CAPITAL LETTERS\n"
        "- Use section headings in CAPITAL LETTERS (e.g. KEY CONCEPTS, "
        "IMPORTANT TERMS, EXAMPLES, QUICK REVISION POINTS)\n"
        "- Under each heading use short bullet points starting with '- '\n"
        "- Leave a blank line between sections\n"
        "- Do not use symbols like ** or #"
    )
    notes = ask_gemini(prompt)
    header = f"STUDYMATE AI - STUDY NOTES\nTopic: {topic}\n" + "=" * 40 + "\n\n"
    return header + notes


def create_study_plan(subjects, hours_per_day, exam_date):
    """Tool 5: Create a study timetable. Dates and hours are worked out in Python."""
    if not subjects or not str(subjects).strip():
        return "Error: please tell me which subjects you want to study."

    # Check study hours
    try:
        hours_per_day = float(hours_per_day)
    except (ValueError, TypeError):
        return "Error: study hours per day must be a number, like 3."
    if hours_per_day <= 0 or hours_per_day > 16:
        return "Error: study hours per day must be between 0 and 16."

    # Check exam date
    try:
        exam_day = datetime.strptime(str(exam_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: the exam date must look like 2026-12-20 (year-month-day)."
    days_left = (exam_day - date.today()).days
    if days_left < 1:
        return "Error: the exam date must be in the future."

    # Simple calculations done by Python
    subject_list = [s.strip() for s in str(subjects).split(",") if s.strip()]
    if not subject_list:
        return "Error: please list your subjects separated by commas."
    total_hours = round(days_left * hours_per_day, 1)
    hours_per_subject = round(total_hours / len(subject_list), 1)

    prompt = (
        "Create a realistic study timetable for a student.\n"
        f"- Today's date: {date.today()}\n"
        f"- Exam date: {exam_day} ({days_left} days left)\n"
        f"- Subjects: {', '.join(subject_list)}\n"
        f"- Study time available: {hours_per_day} hours per day "
        f"(about {total_hours} hours in total, about {hours_per_subject} hours "
        "per subject)\n\n"
        "Rules:\n"
        "- If there are 14 days or fewer, give a day-by-day plan. Otherwise "
        "give a week-by-week plan plus a sample daily routine.\n"
        "- Mix the subjects so the student does not get bored.\n"
        "- Include short breaks and keep the last 1-2 days for revision.\n"
        "- Present the plan as a markdown table, then add 3 short study tips."
    )
    return ask_gemini(prompt)


# Operators the calculator is allowed to use
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}


def evaluate_math_node(node):
    """Safely calculate a parsed math expression (no eval(), so it is secure)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
        left = evaluate_math_node(node.left)
        right = evaluate_math_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("The power is too large.")
        return ALLOWED_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = evaluate_math_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    raise ValueError("Only numbers and + - * / % // ** ( ) are allowed.")


def calculate(expression):
    """Tool 6: Calculator for basic maths."""
    if not expression or not str(expression).strip():
        return "Error: please give me a calculation, like 25 * 4 + 10."
    cleaned = str(expression).replace("^", "**").replace("x", "*").replace("×", "*")
    cleaned = cleaned.replace("÷", "/").replace(",", "")
    try:
        tree = ast.parse(cleaned.strip(), mode="eval")
        result = evaluate_math_node(tree.body)
    except ZeroDivisionError:
        return "Error: you cannot divide by zero."
    except (SyntaxError, ValueError) as error:
        return f"Error: I could not calculate that. {error}"
    if isinstance(result, float):
        result = round(result, 10)
        if result.is_integer():
            result = int(result)
    return f"{expression} = {result}"


# ---------------------------------------------------------------
# PART 3: TOOL DECLARATIONS (what Gemini reads to choose a tool)
# ---------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "explain_topic",
        "description": "Explains an educational topic in simple language with "
                       "examples. Use when the student wants to understand or "
                       "learn a concept.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic to explain"},
                "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"],
                          "description": "Student's level. Default beginner."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "generate_quiz",
        "description": "Creates multiple-choice quiz questions (without answers) "
                       "on a topic. Use when the student wants a quiz or practice questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Quiz topic"},
                "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"],
                               "description": "Difficulty level. Default medium."},
                "num_questions": {"type": "integer",
                                  "description": "Number of questions (1-15). Default 5."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "evaluate_quiz",
        "description": "Checks the student's answers to a quiz, calculates marks "
                       "and gives feedback. Use after the student submits answers.",
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_questions": {"type": "string",
                                   "description": "The complete quiz questions with options, copied from the conversation"},
                "student_answers": {"type": "string",
                                    "description": "The student's answers, e.g. '1-A, 2-C, 3-B'"},
            },
            "required": ["quiz_questions", "student_answers"],
        },
    },
    {
        "name": "generate_study_notes",
        "description": "Creates well-organised revision notes on a topic that the "
                       "student can download. Use when the student asks for notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic for the notes"},
                "detail_level": {"type": "string", "enum": ["short", "standard", "detailed"],
                                 "description": "How detailed the notes should be. Default standard."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "create_study_plan",
        "description": "Creates a study timetable from subjects, daily study hours "
                       "and exam date. Use when the student wants a study plan or timetable.",
        "parameters": {
            "type": "object",
            "properties": {
                "subjects": {"type": "string",
                             "description": "Subjects separated by commas, e.g. 'Maths, Physics'"},
                "hours_per_day": {"type": "number", "description": "Study hours available per day"},
                "exam_date": {"type": "string", "description": "Exam date in YYYY-MM-DD format"},
            },
            "required": ["subjects", "hours_per_day", "exam_date"],
        },
    },
    {
        "name": "calculate",
        "description": "Calculates a mathematical expression using + - * / % // ** "
                       "and brackets. Use for any arithmetic.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "The expression, e.g. '(25 * 4) + 18'"},
            },
            "required": ["expression"],
        },
    },
]

# Connects a tool name (text) to the real Python function
TOOL_FUNCTIONS = {
    "explain_topic": explain_topic,
    "generate_quiz": generate_quiz,
    "evaluate_quiz": evaluate_quiz,
    "generate_study_notes": generate_study_notes,
    "create_study_plan": create_study_plan,
    "calculate": calculate
