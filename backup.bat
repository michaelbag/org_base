@echo off
REM Скрипт для создания резервной копии рабочих данных в виртуальной среде (Windows)

cd /d "%~dp0"

REM Проверка наличия виртуальной среды
if not exist "venv" (
    echo Виртуальная среда не найдена. Создаю...
    python -m venv venv
    if errorlevel 1 (
        echo Ошибка при создании виртуальной среды
        exit /b 1
    )
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Проверка успешной активации
if "%VIRTUAL_ENV%"=="" (
    echo Ошибка: виртуальная среда не активирована
    exit /b 1
)

REM Запуск резервного копирования с переданными аргументами
python scripts\backup_restore.py backup %*

