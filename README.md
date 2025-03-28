# Cosmetic Formula Lab

Cosmetic Formula Lab is an application for creating and managing cosmetic formulations with AI-powered formula generation. The application allows users to build custom skincare formulations, manage ingredients, and access educational resources.

## Project Structure

The project is divided into two main parts:

- **Frontend**: React/TypeScript application with Tailwind CSS for styling
- **Backend**: FastAPI Python application with SQLAlchemy for database access

## Features

- User authentication and authorization
- Subscription management with different user tiers
- Interactive formula builder
- AI-powered formula generation
- Comprehensive ingredient database
- Formula storage and management
- Learning resources for cosmetic formulation

## Getting Started

### Prerequisites

- Node.js (>= 14.x)
- Python (>= 3.8)

### Backend Setup

#### Option 1: Using the Startup Script (Recommended)

1. Navigate to the backend directory:

```bash
cd backend
```

2. Create a `.env` file in the backend directory with the following content:

```
DATABASE_URL=sqlite:///./cosmetic_formula_lab.db
SECRET_KEY=your_secret_key_for_jwt_tokens
DEBUG=True
```

3. Run the startup script:

For Linux/Mac:
```bash
chmod +x startup.sh  # Make the script executable (first time only)
./startup.sh
```

For Windows:
```
startup.bat
```

This script will:
- Create a virtual environment if it doesn't exist
- Install dependencies
- Seed the database with sample data if needed
- Start the FastAPI server

#### Option 2: Manual Setup

1. Navigate to the backend directory:

```bash
cd backend
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory with the following content:

```
DATABASE_URL=sqlite:///./cosmetic_formula_lab.db
SECRET_KEY=your_secret_key_for_jwt_tokens
DEBUG=True
```

5. Seed the database with initial data (users and ingredients):

```bash
python seed_db.py
```

This will create:
- 3 sample users with different subscription levels (admin@example.com, premium@example.com, free@example.com) - all with password "password"
- A variety of ingredients for formulation

6. Run the backend server:

```bash
uvicorn main:app --reload
```

The SQLite database file will be automatically created in the project directory, and all tables will be created on startup.

The API will be available at http://localhost:8000 with Swagger documentation at http://localhost:8000/docs.

### Frontend Setup

1. Navigate to the frontend directory:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
```

3. Create a `.env` file in the frontend directory with the following content:

```
VITE_API_BASE_URL=http://localhost:8000/api
```

4. Run the development server:

```bash
npm run dev
```

The application will be available at http://localhost:5173.

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and get access token
- `GET /api/auth/me` - Get current user information

### Formulas

- `GET /api/formulas` - Get all formulas for current user
- `POST /api/formulas` - Create a new formula
- `GET /api/formulas/{formula_id}` - Get a specific formula
- `PUT /api/formulas/{formula_id}` - Update a formula
- `DELETE /api/formulas/{formula_id}` - Delete a formula

### Ingredients

- `GET /api/ingredients` - Get all ingredients
- `GET /api/ingredients/{ingredient_id}` - Get a specific ingredient
- `GET /api/ingredients/phases` - Get all ingredient phases
- `GET /api/ingredients/functions` - Get all ingredient functions

### AI Formula Generation

- `POST /api/ai-formula/generate` - Generate a formula using AI
- `GET /api/ai-formula/compatibility` - Check ingredient compatibility

### User Management

- `GET /api/users/me` - Get current user information
- `PUT /api/users/me` - Update user information
- `PUT /api/users/me/password` - Update user password
- `POST /api/users/subscription` - Update user subscription

## Deployment

### Backend Deployment

The backend is configured for deployment on Railway.app:

1. Create a new project on Railway
2. Connect your GitHub repository
3. Add PostgreSQL plugin
4. Configure environment variables
5. Deploy

### Frontend Deployment

The frontend is configured for deployment on Vercel:

1. Create a new project on Vercel
2. Connect your GitHub repository
3. Configure environment variables
4. Deploy

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/my-new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.