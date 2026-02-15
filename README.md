# University Attendance System

This is a web application for managing university attendance with user authentication.

## Features
- User registration and login
- Role-based access (student, teacher, admin, dean)
- User dashboard with profile information
- Attendance tracking system

## How to Run

1. Make sure you have Docker and Docker Compose installed
2. Run the following command to start the application:

```bash
docker-compose up --build
```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API docs: http://localhost:8000/docs

## Development

To develop locally:
1. For backend development, install the requirements from `/backend/requirements.txt`
2. For frontend development, navigate to `/frontend` and run `npm install` followed by `npm run dev`

## Technologies Used

- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL
- Frontend: HTML, CSS, JavaScript, Express.js
- Deployment: Docker, Docker Compose