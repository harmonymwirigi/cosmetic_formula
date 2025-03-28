@echo off
REM backend/startup.bat

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Seed the database if it doesn't exist
if not exist "cosmetic_formula_lab.db" (
    echo Seeding the database...
    python seed_db.py
)

REM Start the server
echo Starting FastAPI server...
uvicorn main:app --reload