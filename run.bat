@echo off
if not exist .venv\Scripts\activate.bat (
  echo Create a virtual environment and install requirements first. See README.md.
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload
