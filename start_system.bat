@echo off

REM Start Ship Traffic Visualization System

REM Create log directory if not exists
if not exist "logs" mkdir logs

REM Start backend service in a new window
start "Backend Service" cmd /k "cd backend && python -m venv venv && venv\Scripts\activate && pip install fastapi uvicorn prisma python-dotenv pydantic && python -m prisma generate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ..\logs\backend.log 2>&1"

REM Wait for 5 seconds to ensure backend starts first
echo Waiting for backend service to initialize...
timeout /t 5 /nobreak > nul

REM Start frontend service in a new window
start "Frontend Service" cmd /k "cd frontend && npm install && npm run dev > ..\logs\frontend.log 2>&1"

REM Open the application in default browser
echo System is starting... Please wait for a moment...
timeout /t 10 /nobreak > nul
start http://localhost:3000

REM Show instructions
echo.
echo System is starting. Check the progress in the opened windows.
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.
echo Press any key to exit this window...
pause > nul