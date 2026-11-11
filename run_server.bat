@echo off
title Servidor BreakApp-AI (Puerto 8000)
echo ========================================================
echo   Iniciando Microservicio del Agente Break IA...
echo   Puerto: 8000 (Accesible desde emulador en 10.0.2.2:8000)
echo ========================================================
python server.py 8000
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo iniciar con 'python'. Intentando con 'py'...
    py server.py 8000
)
pause