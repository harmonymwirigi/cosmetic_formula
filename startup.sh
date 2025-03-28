#!/bin/bash
# backend/startup.sh

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check and create required structure
echo "Checking directory structure..."
python check_structure.py

# Seed the database if it doesn't exist
if [ ! -f "cosmetic_formula_lab.db" ]; then
    echo "Seeding the database..."
    python seed_db.py
fi

# Start the server
echo "Starting FastAPI server..."
uvicorn main:app --reload#!/bin/bash
# backend/startup.sh

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Seed the database if it doesn't exist
if [ ! -f "cosmetic_formula_lab.db" ]; then
    echo "Seeding the database..."
    python seed_db.py
fi

# Start the server
echo "Starting FastAPI server..."
uvicorn main:app --reload