# StudyMate AI 🎓

An AI study agent built with Python, Streamlit and Google Gemini. The agent
reads a student's request, chooses a tool (a Python function), runs it and
replies with the result.

## Files
| File | Purpose |
|------|---------|
| `app.py` | The website: layout, styling, chat screen, sidebar, download button |
| `agent.py` | The agent loop: sends messages to Gemini, runs the tools Gemini picks |
| `tools.py` | The 6 tools, Gemini helper functions and tool descriptions |
| `requirements.txt` | Libraries to install |
| `.gitignore` | Stops secret files from going to GitHub |
| `.streamlit/config.toml` | Light theme colours |

## Tools
Topic Explainer, Quiz Generator, Quiz Evaluator, Study Notes Generator
(download as .txt), Study Planner, Calculator.

## Run locally
1. Install Python 3.10 or newer.
2. `pip install -r requirements.txt`
3. Get a free key at https://aistudio.google.com/app/apikey
   (do NOT enable billing).
4. Create the file `.streamlit/secrets.toml` and add:
   ```
   GEMINI_API_KEY = "paste-your-key-here"
   ```
   (Optional: `GEMINI_MODEL = "model-name-from-AI-Studio"`)
5. `streamlit run app.py`

## Deploy free on Streamlit Community Cloud
1. Upload the project to a public GitHub repository.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click Create app, choose your repo, branch `main`, main file `app.py`.
4. Open Advanced settings > Secrets and paste:
   `GEMINI_API_KEY = "your-key"`
5. Click Deploy and share the link you get.

## Limits
Gemini's free tier has request limits. If you see a "limit reached" message,
wait a minute. Free apps on Streamlit Cloud sleep when unused and wake up
when opened.
