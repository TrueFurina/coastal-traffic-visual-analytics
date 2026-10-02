@echo off
echo 启动船舶交通流可视化系统...

echo.
echo 1. 启动后端服务 (FastAPI + DuckDB)...
cd backend
start "Backend Server" cmd /k "venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd ..

echo.
echo 2. 等待后端启动...
timeout /t 3 /nobreak > nul

echo.
echo 3. 启动前端服务...
cd frontend
start "Frontend Server" cmd /k "npm run dev"
cd ..

echo.
echo 系统启动完成！
echo 后端服务: http://localhost:8000
echo 前端服务: http://localhost:3000
echo.
echo 按任意键退出...
pause > nul
