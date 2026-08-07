@echo off
cd /d "%~dp0"

echo Installiere Abhaengigkeiten...

if not exist ".venv" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo Starte StockMind auf http://localhost:8501 ...
streamlit run app.py

pause
