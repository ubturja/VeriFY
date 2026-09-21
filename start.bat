@echo off
echo ==========================================
echo Starting VeriFY Setup and Services
echo ==========================================
echo.

:: Check if uv is installed, if not, install it
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [1/3] 'uv' is not installed. Installing 'uv' via PowerShell...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo Please restart this script after installation finishes so 'uv' is recognized!
    pause
    exit /b
) else (
    echo [1/3] 'uv' is already installed.
)

:: Run Backend Setup
echo [2/3] Setting up Python backend...
cd backend
call uv sync
echo Starting backend server in a new window...
start cmd /k "echo Starting Backend API... && uv run uvicorn verify.api.app:app --reload --host 0.0.0.0 --port 8000"
cd ..

:: Run Frontend Setup
echo [3/3] Setting up React frontend...
cd console
call npm install
echo Starting frontend server in a new window...
start cmd /k "echo Starting React Console... && npm run dev"
cd ..

echo.
echo ==========================================
echo All services launched! 
echo Dashboard: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo ==========================================
pause
