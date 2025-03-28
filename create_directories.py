# backend/create_directories.py
import os

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

# Create required directories
create_directory("app/api")
create_directory("app/api/endpoints")