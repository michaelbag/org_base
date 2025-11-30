# Виртуальная среда Python

## Важно!

**Все скрипты Python в этом проекте должны запускаться в активированной виртуальной среде!**

## Создание виртуальной среды

Если виртуальная среда еще не создана:

**macOS/Linux:**
```bash
python3 -m venv venv
```

**Windows:**
```bash
python -m venv venv
```

## Активация виртуальной среды

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

После активации в начале строки терминала появится `(venv)`.

## Деактивация

Для деактивации виртуальной среды просто выполните:
```bash
deactivate
```

## Установка зависимостей

После создания и активации виртуальной среды установите зависимости:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Использование скриптов-оберток

Для удобства созданы скрипты-обертки, которые автоматически активируют виртуальную среду:

**macOS/Linux:**
```bash
./run_server.sh        # Запуск веб-сервера
./generate_pdf.sh      # Генерация PDF
```

**Windows:**
```cmd
run_server.bat         # Запуск веб-сервера
generate_pdf.bat       # Генерация PDF
```

Эти скрипты автоматически:
1. Проверяют наличие виртуальной среды
2. Создают её, если отсутствует
3. Активируют виртуальную среду
4. Устанавливают зависимости, если нужно
5. Запускают соответствующий скрипт

## Ручной запуск скриптов

Если вы запускаете скрипты вручную, всегда убедитесь, что виртуальная среда активирована:

```bash
# Активируйте виртуальную среду
source venv/bin/activate  # macOS/Linux
# или
venv\Scripts\activate     # Windows

# Затем запускайте скрипты
python scripts/server.py
python scripts/generate_pdf.py
python scripts/init_history.py
```

## Проверка активации

Чтобы проверить, что виртуальная среда активирована:

```bash
which python    # macOS/Linux - должен показать путь к venv/bin/python
where python    # Windows - должен показать путь к venv\Scripts\python.exe
```

Также можно проверить переменную окружения:
```bash
echo $VIRTUAL_ENV  # macOS/Linux
echo %VIRTUAL_ENV%  # Windows
```

## Обновление зависимостей

Если `requirements.txt` был обновлен:

```bash
source venv/bin/activate  # Активируйте виртуальную среду
pip install -r requirements.txt --upgrade
```

## Структура виртуальной среды

Виртуальная среда создается в папке `venv/` в корне проекта:
- `venv/` - не коммитится в Git (указано в `.gitignore`)
- Каждый разработчик создает свою виртуальную среду локально
- Зависимости устанавливаются из `requirements.txt`

