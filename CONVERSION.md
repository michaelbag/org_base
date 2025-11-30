# Конвертация документов в HTML и PDF

Система поддерживает конвертацию документов из Markdown в HTML и PDF форматы с возможностью выборочной конвертации по различным фильтрам.

## Быстрый старт

### Конвертация всех документов

```bash
# Конвертация в HTML и PDF (по умолчанию)
./convert_documents.sh

# Только HTML
./convert_documents.sh --formats html

# Только PDF
./convert_documents.sh --formats pdf
```

### Выборочная конвертация

```bash
# По организации
./convert_documents.sh --organization "ООО ФК РАНА"

# По отделу
./convert_documents.sh --department "Отдел информационных технологий"

# По типу документа
./convert_documents.sh --type "положение"

# По статусу
./convert_documents.sh --status "действующий"

# Комбинация фильтров
./convert_documents.sh \
  --organization "ООО ФК РАНА" \
  --department "Отдел информационных технологий" \
  --formats pdf
```

## Использование через Python

```python
from scripts.document_converter import DocumentConverter

# Создание конвертера
converter = DocumentConverter(
    documents_dir="documents",
    html_dir="html",
    pdf_dir="pdf"
)

# Конвертация всех документов
converter.convert_all(formats=['html', 'pdf'])

# Выборочная конвертация
converter.convert_filtered(
    organization="ООО ФК РАНА",
    department="Отдел информационных технологий",
    doc_type="положение",
    formats=['html', 'pdf']
)

# Конвертация конкретного списка документов
documents = converter.parser.filter_documents(
    organization="ООО ФК РАНА"
)
converter.convert_documents(documents, formats=['pdf'])
```

## API Endpoints

### Конвертация с фильтрами

```http
POST /api/convert
Content-Type: application/json

{
  "formats": ["html", "pdf"],
  "organization": "ООО ФК РАНА",
  "department": "Отдел информационных технологий",
  "type": "положение",
  "status": "действующий"
}
```

### Конвертация одного документа

```http
POST /api/convert/ООО ФК РАНА/Отдел информационных технологий/положения/положение-об-отделе-информационных-технологий.md
Content-Type: application/json

{
  "formats": ["html", "pdf"]
}
```

## Параметры командной строки

```
--formats {html, pdf} [{html, pdf} ...]
                        Форматы для конвертации (по умолчанию: html pdf)
--organization ORGANIZATION
                        Фильтр по организации
--department DEPARTMENT
                        Фильтр по отделу
--type TYPE             Фильтр по типу документа
--status STATUS         Фильтр по статусу документа
--documents-dir DIR     Директория с документами (по умолчанию: documents)
--html-dir DIR          Директория для HTML файлов (по умолчанию: html)
--pdf-dir DIR           Директория для PDF файлов (по умолчанию: pdf)
--quiet                 Минимальный вывод (только ошибки)
```

## Структура выходных файлов

HTML и PDF файлы сохраняются в соответствующих директориях с сохранением структуры исходных документов:

```
documents/
  └── ООО ФК РАНА/
      └── Отдел информационных технологий/
          └── положения/
              └── положение-об-отделе.md

html/
  └── ООО ФК РАНА/
      └── Отдел информационных технологий/
          └── положения/
              └── положение-об-отделе.html

pdf/
  └── ООО ФК РАНА/
      └── Отдел информационных технологий/
          └── положения/
              └── положение-об-отделе.pdf
```

## Требования

- Python 3.7+
- Установленные зависимости из `requirements.txt`
- Для генерации PDF: `wkhtmltopdf` (установка: `brew install wkhtmltopdf` на macOS)

## Обратная совместимость

Старый скрипт `generate_pdf.py` продолжает работать и теперь использует новый конвертер под капотом:

```bash
./generate_pdf.sh  # Генерирует только PDF для всех документов
```

