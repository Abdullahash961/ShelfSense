@echo off
echo ========================================================
echo        ShelfSense Prototype - Startup Script
echo ========================================================
echo.

:: Check if Python virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. 
    echo Please run: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b
)

:: Check if node_modules exists
if not exist "dashboard\node_modules" (
    echo [ERROR] Node modules not found in dashboard folder.
    echo Please run: cd dashboard ^&^& npm install
    pause
    exit /b
)

echo [1/3] Starting FastAPI Backend on Port 8000...
start cmd /k ".\.venv\Scripts\activate.bat && python -m uvicorn app:app --reload"

echo [2/3] Starting React Dashboard on Port 5173...
start cmd /k "cd dashboard && npm run dev"

echo [3/3] Opening browser...
timeout /t 3 >nul
start http://localhost:5173

echo.
echo ========================================================
echo ShelfSense is now running!
echo Do not close the two terminal windows that just opened.
echo ========================================================
pause
