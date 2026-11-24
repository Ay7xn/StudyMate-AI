# agent.py
# The "brain" of StudyMate AI. It runs the agent loop:
#   1. Send the student's message + tool list to Gemini
#   2. If Gemini asks for a tool -> run it with Python
#   3. Send the tool result back to Gemini
#   4. Repeat until Gemini gives a final text answer

from datetime import date

from google.genai import types

from tools import TOOL_DECLARATIONS, call_gemini, friendly_error, run_tool

MAX_TOOL_ROUNDS = 5        # safety limit so the loop can never run forever
MAX_HISTORY_MESSAGES = 12  # how many old messages the agent remembers


def build_system_prompt():
    """Instructions that tell Gemini how to behave as StudyMate AI."""
    return f"""You are StudyMate AI, a friendly and encouraging study assistant for students.
Today's date is {date.today()}.

You have tools: explain_topic, generate_quiz, evaluate_quiz, generate_study_notes,
create_study_plan and calculate. Choose the tool that matches the student's request.

Rules:
1. Use the calculate tool for any arithmetic. Do not do maths in your head.
2. For quizzes, call generate_quiz, then show the questions exactly as returned.
   Never reveal the answers. Tell the student to reply like: 1-A, 2-C, 3-B.
3. When the student sends quiz answers, call evaluate_quiz. Pass the FULL quiz
   questions from the conversation and the student's answers.
4. For notes, call generate_study_notes, show the notes, and tell the student they
   can download them using the download button under your message.
5. For a study plan you need: subjects, study hours per day and exam date. If
   something is missing, ask the student politely. Convert the date to YYYY-MM-DD.
6. For greetings or general study advice, answer directly without a tool.
7. Show the tool's result to the student in full (you may format it nicely).
8. If a tool returns an error, explain it simply and say how to fix it.
9. Keep your tone friendly and clear. Use markdown formatting."""


def history_to_contents(chat_history):
    """Convert old chat messages into the format Gemini understands."""
    contents = []
    for message in chat_history[-MAX_HISTORY_MESSAGES:]:
        role = "user" if message["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=message["content"])])
        )
    return contents


def run_agent(user_message, chat_history):
    """
    Main agent function.
    Returns a dictionary: {"text": answer, "tools_used": [...], "notes": notes or None}
    """
    tools_used = []
    notes_text = None

    # Conversation = old messages + the new message
    contents = history_to_contents(chat_history)
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    )

    # Give Gemini the tool list. Automatic calling is OFF, so WE run the tools
    # ourselves, which makes the agent logic easy to see and explain.
    config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(),
        tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = call_gemini(contents, config)

            # Safely get the parts of Gemini's reply
            if not response.candidates or response.candidates[0].content is None:
                return {"text": "I could not answer that. Please rephrase your question.",
                        "tools_used": tools_used, "notes": notes_text}
            reply_content = response.candidates[0].content
            parts = reply_content.parts or []

            # Did Gemini ask us to run any tools?
            tool_calls = [part.function_call for part in parts if part.function_call]

            # No tool requested -> this is the final answer
            if not tool_calls:
                final_text = "".join(
                    part.text for part in parts
                    if part.text and not getattr(part, "thought", False)
                ).strip()
                if not final_text:
                    final_text = "Done! Let me know what you would like to study next."
                return {"text": final_text, "tools_used": tools_used, "notes": notes_text}

            # Keep Gemini's request in the conversation
            contents.append(reply_content)

            # Run each requested tool and send the results back
            result_parts = []
            for call in tool_calls:
                result = run_tool(call.name, dict(call.args or {}))
                tools_used.append(call.name)
                if call.name == "generate_study_notes" and not result.startswith("Error"):
                    notes_text = result  # saved so the app can offer a download
                result_parts.append(
                    types.Part.from_function_response(
                        name=call.name, response={"result": result}
                    )
                )
            contents.append(types.Content(role="user", parts=result_parts))

        return {"text": "That request needed too many steps. Please try a simpler request.",
                "tools_used": tools_used, "notes": notes_text}

    except Exception as error:
        return {"text": "⚠️ " + friendly_error(error),
                "tools_used": tools_used, "notes": notes_text}
