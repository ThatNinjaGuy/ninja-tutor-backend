# Ninja Tutor Backend

A FastAPI-based backend for the Ninja Tutor educational platform with Firebase integration and AI-powered features.

## Features

- 📚 **Book Management**: Upload, process, and manage educational content (PDF, EPUB, DOCX)
- 🤖 **AI Integration**: OpenAI-powered definitions, explanations, and quiz generation
- 📝 **Notes & Annotations**: Smart note-taking with AI insights
- 🧪 **Quiz System**: Auto-generated quizzes with multiple question types
- 👤 **User Management**: JWT-based authentication and user profiles
- ☁️ **Firebase Integration**: Firestore for data storage, Firebase Storage for files
- 🔍 **Search**: Content search across books and notes

## Quick Start

### Prerequisites

- Python 3.8+
- Firebase project with Firestore and Storage enabled
- OpenAI API key

### Installation

1. Clone and navigate to the backend directory:
```bash
cd ninja_tutor_backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp env_example .env
# Edit .env with your Firebase and OpenAI credentials
```

4. Run the development server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Interactive API docs: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

## Configuration

### Environment Variables

Copy `env_example` to `.env` and configure:

```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key

# App Configuration
DEBUG=True
HOST=0.0.0.0
PORT=8000
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/profile` - Get user profile
- `PUT /api/v1/auth/profile` - Update user profile

### Books
- `POST /api/v1/books/upload` - Upload a book file
- `GET /api/v1/books` - Get books list
- `GET /api/v1/books/{book_id}` - Get specific book
- `GET /api/v1/books/search?q=query` - Search books
- `DELETE /api/v1/books/{book_id}` - Delete book

### AI Features
- `POST /api/v1/ai/definition` - Get AI-powered definitions
- `POST /api/v1/ai/explanation` - Get concept explanations
- `POST /api/v1/ai/generate-questions` - Generate practice questions
- `POST /api/v1/ai/comprehension` - Analyze reading comprehension
- `POST /api/v1/ai/insights` - Generate AI insights for notes

### Quizzes
- `POST /api/v1/quizzes/generate` - Generate quiz from content
- `GET /api/v1/quizzes/{quiz_id}` - Get quiz
- `POST /api/v1/quizzes/{quiz_id}/submit` - Submit quiz answers
- `GET /api/v1/quizzes/stats/{user_id}` - Get quiz statistics

### Notes
- `POST /api/v1/notes` - Create note
- `GET /api/v1/notes/book/{book_id}` - Get notes for book
- `GET /api/v1/notes/{note_id}` - Get specific note
- `PUT /api/v1/notes/{note_id}` - Update note
- `DELETE /api/v1/notes/{note_id}` - Delete note
- `GET /api/v1/notes/shared/{book_id}` - Get shared notes

## Project Structure

```
ninja_tutor_backend/
├── app/
│   ├── api/v1/endpoints/     # API route handlers
│   ├── core/                 # Core configuration
│   ├── models/               # Pydantic data models
│   └── services/             # Business logic services
├── uploads/                  # Temporary file uploads
├── main.py                   # FastAPI application
├── requirements.txt          # Python dependencies
└── README.md
```

## Firebase Setup

1. Create a Firebase project at https://console.firebase.google.com
2. Enable Firestore Database
3. Enable Firebase Storage
4. Generate a service account key:
   - Go to Project Settings → Service Accounts
   - Generate new private key
   - Extract the credentials for your `.env` file

## Testing

The API includes example data and can be tested using the interactive documentation at `/docs`.

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in environment
2. Configure proper CORS origins
3. Use a production WSGI server like Gunicorn
4. Set up proper Firebase security rules
5. Configure rate limiting and monitoring

## Support

For issues and questions, refer to the API documentation or check the logs for detailed error messages.
