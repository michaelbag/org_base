#!/bin/bash
# Скрипт для запуска веб-сервера в виртуальной среде

cd "$(dirname "$0")"

# Проверка наличия виртуальной среды
if [ ! -d "venv" ]; then
    echo "Виртуальная среда не найдена. Создаю..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Ошибка при создании виртуальной среды"
        exit 1
    fi
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Проверка успешной активации
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ошибка: виртуальная среда не активирована"
    exit 1
fi

# Запуск сервера
python scripts/server.py

