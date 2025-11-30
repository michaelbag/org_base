@echo off
REM Скрипт для запуска веб-сервера в виртуальной среде (Windows)

cd /d "%~dp0"

REM Проверка наличия виртуальной среды
if not exist "venv" (
    echo Виртуальная среда не найдена. Создаю...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Запуск сервера
python scripts\server.py

