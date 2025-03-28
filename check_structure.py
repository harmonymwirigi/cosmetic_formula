# backend/check_structure.py
import os

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

# List of directories that should exist
required_dirs = [
    "app",
    "app/api",
    "app/api/endpoints",
    "app/services"
]

# Create required directories
for directory in required_dirs:
    create_directory(directory)

# List of files that should exist
required_files = [
    ("app/__init__.py", "# This file makes the directory a Python package"),
    ("app/api/__init__.py", "# This file makes the directory a Python package"),
    ("app/api/endpoints/__init__.py", "# This file makes the directory a Python package"),
    ("app/services/__init__.py", "# This file makes the directory a Python package")
]

# Create required files
for file_path, content in required_files:
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Created file: {file_path}")
    else:
        print(f"File already exists: {file_path}")

print("Directory structure check completed.")