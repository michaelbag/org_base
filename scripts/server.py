"""
Веб-сервер для просмотра документов

Версия: 0.0.1.5
Лицензия: LGPL-3.0
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from document_parser import DocumentParser
from version_tracker import VersionTracker
from document_converter import DocumentConverter
import markdown2

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), '..', 'web', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'web', 'static'))

# Инициализация парсера, трекера версий и конвертера
BASE_DIR = Path(__file__).parent.parent
parser = DocumentParser(str(BASE_DIR / "documents"))
version_tracker = VersionTracker(str(BASE_DIR / "documents"), str(BASE_DIR / "version_history"))
converter = DocumentConverter(
    documents_dir=str(BASE_DIR / "documents"),
    html_dir=str(BASE_DIR / "html"),
    pdf_dir=str(BASE_DIR / "pdf")
)


@app.route('/')
def index():
    """Главная страница с формой навигации"""
    organizations = parser.get_organizations()
    document_types = parser.get_document_types()
    
    return render_template('index.html',
                         organizations=organizations,
                         document_types=document_types)


@app.route('/api/organizations')
def api_organizations():
    """API: список организаций"""
    return jsonify(parser.get_organizations())


@app.route('/api/departments')
def api_departments():
    """API: список отделов"""
    organization = request.args.get('organization')
    departments = parser.get_departments(organization)
    return jsonify(departments)


@app.route('/api/documents')
def api_documents():
    """API: список документов с фильтрацией"""
    organization = request.args.get('organization')
    department = request.args.get('department')
    doc_type = request.args.get('type')
    status = request.args.get('status')
    
    documents = parser.filter_documents(
        organization=organization,
        department=department,
        doc_type=doc_type,
        status=status
    )
    
    # Убираем содержимое из списка для экономии трафика
    for doc in documents:
        if 'content' in doc:
            del doc['content']
    
    return jsonify(documents)


def format_date_for_display(date_value):
    """Форматирует дату в формат дд.ММ.ГГГГ для отображения"""
    if not date_value:
        return None
    
    # Если это объект date или datetime
    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%d.%m.%Y')
    
    # Преобразуем в строку, если нужно
    date_str = str(date_value)
    
    # Если уже в формате дд.ММ.ГГГГ, возвращаем как есть
    if '.' in date_str and len(date_str.split('.')) == 3:
        parts = date_str.split('.')
        if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) == 4:
            return date_str
    
    # Пробуем распарсить ISO формат (YYYY-MM-DD)
    try:
        if '-' in date_str:
            date_part = date_str.split()[0] if ' ' in date_str else date_str
            dt = datetime.strptime(date_part, '%Y-%m-%d')
            return dt.strftime('%d.%m.%Y')
    except (ValueError, AttributeError, TypeError):
        pass
    
    # Пробуем другие форматы
    formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            date_part = date_str.split()[0] if ' ' in date_str else date_str
            dt = datetime.strptime(date_part, fmt)
            return dt.strftime('%d.%m.%Y')
        except (ValueError, AttributeError, TypeError):
            continue
    
    # Если не удалось распарсить, возвращаем как есть
    return date_str


@app.route('/document/<path:doc_path>')
def view_document(doc_path):
    """Просмотр документа"""
    doc_file = BASE_DIR / "documents" / doc_path
    
    if not doc_file.exists() or not doc_file.suffix == '.md':
        return "Документ не найден", 404
    
    document = parser.parse_document(doc_file)
    if not document:
        return "Ошибка при чтении документа", 500
    
    # Форматируем даты для отображения
    if 'approved_date' in document:
        document['approved_date'] = format_date_for_display(document['approved_date'])
    if 'effective_date' in document:
        document['effective_date'] = format_date_for_display(document['effective_date'])
    if 'expiry_date' in document:
        document['expiry_date'] = format_date_for_display(document['expiry_date'])
    if 'date' in document:
        document['date'] = format_date_for_display(document['date'])
    
    # Обрабатываем ссылки на документы в Markdown перед конвертацией
    markdown_content = _process_document_links_in_markdown(
        document['content'],
        doc_path,
        document
    )
    
    # Конвертируем Markdown в HTML
    html_content = markdown2.markdown(
        markdown_content,
        extras=['fenced-code-blocks', 'tables', 'header-ids']
    )
    
    # Обрабатываем ссылки на другие документы в HTML (на случай, если что-то пропустили)
    html_content = _process_document_links_in_html(
        html_content, 
        doc_path, 
        document
    )
    
    # Проверяем наличие PDF
    pdf_path = BASE_DIR / "pdf" / Path(doc_path).with_suffix('.pdf')
    has_pdf = pdf_path.exists()
    
    # Получаем историю изменений
    history = version_tracker.get_history(doc_file)
    
    # Получаем приложения
    attachments = document.get('attachments', [])
    
    # Получаем блок утверждения
    approval_block = document.get('approval_block')
    
    return render_template('document.html',
                         document=document,
                         content=html_content,
                         has_pdf=has_pdf,
                         pdf_path=f"/pdf/{doc_path.replace('.md', '.pdf')}",
                         history=history,
                         doc_path=doc_path,
                         attachments=attachments,
                         approval_block=approval_block)


def _process_document_links_in_markdown(markdown_content: str, doc_path: str, document: dict) -> str:
    """
    Обрабатывает ссылки на другие документы в Markdown контенте
    
    Преобразует ссылки вида [текст](doc:номер) или [текст](doc:путь) в рабочие ссылки
    """
    import re
    from urllib.parse import quote
    
    # Паттерн для поиска ссылок на документы в Markdown: [текст](doc:ссылка)
    pattern = r'\[([^\]]+)\]\(doc:([^\)]+)\)'
    
    def replace_doc_link(match):
        link_text = match.group(1)
        doc_ref = match.group(2).strip()
        
        # Пробуем найти документ
        doc = None
        
        # По номеру
        doc = parser.find_document_by_number(
            doc_ref, 
            document.get('organization')
        )
        
        # По пути
        if not doc:
            doc = parser.find_document_by_path(
                doc_ref,
                doc_path
            )
        
        if doc:
            doc_path_found = doc.get('relative_path', '').replace('\\', '/')
            encoded_path = quote(doc_path_found, safe='/')
            return f'[{link_text}](/document/{encoded_path})'
        else:
            # Если документ не найден, оставляем как есть, но помечаем
            return f'[{link_text}](doc:{doc_ref})'
    
    markdown_content = re.sub(pattern, replace_doc_link, markdown_content)
    
    return markdown_content


def _process_document_links_in_html(html_content: str, doc_path: str, document: dict) -> str:
    """
    Обрабатывает ссылки на другие документы в HTML контенте
    
    Преобразует ссылки вида doc:номер или doc:путь в рабочие ссылки
    """
    import re
    from urllib.parse import quote
    
    # Паттерн для поиска ссылок на документы: [текст](doc:ссылка)
    pattern = r'href=["\']doc:([^"\']+)["\']'
    
    def replace_doc_link(match):
        doc_ref = match.group(1)
        
        # Пробуем найти документ
        doc = None
        
        # По номеру
        if 'number' in document:
            doc = parser.find_document_by_number(
                doc_ref, 
                document.get('organization')
            )
        
        # По пути
        if not doc:
            doc = parser.find_document_by_path(
                doc_ref,
                doc_path
            )
        
        if doc:
            doc_path_found = doc.get('relative_path', '').replace('\\', '/')
            encoded_path = quote(doc_path_found, safe='/')
            return f'href="/document/{encoded_path}"'
        else:
            # Если документ не найден, оставляем ссылку как есть, но помечаем как нерабочую
            return f'href="#" class="broken-doc-link" title="Документ не найден: {doc_ref}"'
    
    html_content = re.sub(pattern, replace_doc_link, html_content)
    
    return html_content


@app.route('/pdf/<path:pdf_path>')
def download_pdf(pdf_path):
    """Скачивание PDF файла"""
    pdf_file = BASE_DIR / "pdf" / pdf_path
    
    if not pdf_file.exists():
        return "PDF файл не найден", 404
    
    return send_file(str(pdf_file), mimetype='application/pdf')


@app.route('/html/<path:html_path>')
def download_html(html_path):
    """Скачивание HTML файла"""
    html_file = BASE_DIR / "html" / html_path
    
    if not html_file.exists():
        return "HTML файл не найден", 404
    
    return send_file(str(html_file), mimetype='text/html')


@app.route('/attachment/<path:doc_path>/<path:attachment_path>')
def download_attachment(doc_path, attachment_path):
    """Скачивание файла приложения к документу"""
    # doc_path может быть с .md или без, нужно нормализовать
    if doc_path.endswith('.md'):
        doc_file = BASE_DIR / "documents" / doc_path
    else:
        # Если без расширения, добавляем .md
        doc_file = BASE_DIR / "documents" / f"{doc_path}.md"
    
    if not doc_file.exists():
        return "Документ не найден", 404
    
    doc_dir = doc_file.parent
    
    # Безопасность: проверяем, что путь не выходит за пределы директории документа
    attachment_file = (doc_dir / attachment_path).resolve()
    doc_dir_resolved = doc_dir.resolve()
    
    # Проверяем, что файл находится внутри директории документа
    try:
        attachment_file.relative_to(doc_dir_resolved)
    except ValueError:
        return "Неверный путь к приложению", 403
    
    if not attachment_file.exists():
        return "Файл приложения не найден", 404
    
    # Определяем MIME тип
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.rtf': 'application/rtf',
    }
    
    mime_type = mime_types.get(attachment_file.suffix.lower(), 'application/octet-stream')
    
    return send_file(str(attachment_file), mimetype=mime_type)


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API: конвертация документов в HTML и/или PDF"""
    data = request.get_json() or {}
    
    # Параметры фильтрации
    organization = data.get('organization')
    department = data.get('department')
    doc_type = data.get('type')
    status = data.get('status')
    
    # Форматы для конвертации
    formats = data.get('formats', ['html', 'pdf'])
    if isinstance(formats, str):
        formats = [formats]
    
    # Валидация форматов
    valid_formats = ['html', 'pdf']
    formats = [f for f in formats if f in valid_formats]
    if not formats:
        return jsonify({'error': 'Не указаны корректные форматы (html, pdf)'}), 400
    
    try:
        # Конвертируем документы
        results = converter.convert_filtered(
            organization=organization,
            department=department,
            doc_type=doc_type,
            status=status,
            formats=formats,
            verbose=False
        )
        
        # Преобразуем Path в строки для JSON
        response = {
            'success': True,
            'formats': formats,
            'results': {
                'html': [str(p.relative_to(BASE_DIR)) for p in results['html']],
                'pdf': [str(p.relative_to(BASE_DIR)) for p in results['pdf']]
            },
            'counts': {
                'html': len(results['html']),
                'pdf': len(results['pdf'])
            }
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/convert/<path:doc_path>', methods=['POST'])
def api_convert_document(doc_path):
    """API: конвертация одного документа"""
    doc_file = BASE_DIR / "documents" / doc_path
    
    if not doc_file.exists() or not doc_file.suffix == '.md':
        return jsonify({'error': 'Документ не найден'}), 404
    
    data = request.get_json() or {}
    formats = data.get('formats', ['html', 'pdf'])
    if isinstance(formats, str):
        formats = [formats]
    
    # Валидация форматов
    valid_formats = ['html', 'pdf']
    formats = [f for f in formats if f in valid_formats]
    if not formats:
        return jsonify({'error': 'Не указаны корректные форматы (html, pdf)'}), 400
    
    try:
        document = parser.parse_document(doc_file)
        if not document:
            return jsonify({'error': 'Ошибка при чтении документа'}), 500
        
        results = {'html': [], 'pdf': []}
        
        if 'html' in formats:
            html_path = converter.generate_html(document)
            if html_path:
                results['html'].append(str(html_path.relative_to(BASE_DIR)))
        
        if 'pdf' in formats:
            pdf_path = converter.generate_pdf(document)
            if pdf_path:
                results['pdf'].append(str(pdf_path.relative_to(BASE_DIR)))
        
        return jsonify({
            'success': True,
            'document': doc_path,
            'formats': formats,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<path:doc_path>')
def api_history(doc_path):
    """API: история изменений документа"""
    doc_file = BASE_DIR / "documents" / doc_path
    
    if not doc_file.exists():
        return jsonify({'error': 'Документ не найден'}), 404
    
    history = version_tracker.get_history(doc_file)
    return jsonify(history)


@app.route('/api/version/<path:doc_path>/<int:version>')
def api_version(doc_path, version):
    """API: получение конкретной версии документа"""
    doc_file = BASE_DIR / "documents" / doc_path
    
    if not doc_file.exists():
        return jsonify({'error': 'Документ не найден'}), 404
    
    version_data = version_tracker.get_document_version(doc_file, version)
    
    if not version_data:
        return jsonify({'error': 'Версия не найдена'}), 404
    
    # Конвертируем Markdown в HTML
    html_content = markdown2.markdown(
        version_data['content'],
        extras=['fenced-code-blocks', 'tables', 'header-ids']
    )
    version_data['html_content'] = html_content
    
    return jsonify(version_data)


@app.route('/version/<path:doc_path>/<int:version>')
def view_version(doc_path, version):
    """Просмотр конкретной версии документа"""
    doc_file = BASE_DIR / "documents" / doc_path
    
    if not doc_file.exists():
        return "Документ не найден", 404
    
    version_data = version_tracker.get_document_version(doc_file, version)
    
    if not version_data:
        return "Версия не найдена", 404
    
    # Конвертируем Markdown в HTML
    html_content = markdown2.markdown(
        version_data['content'],
        extras=['fenced-code-blocks', 'tables', 'header-ids']
    )
    
    return render_template('document_version.html',
                         document=version_data['metadata'],
                         content=html_content,
                         version_info=version_data,
                         doc_path=doc_path)


if __name__ == '__main__':
    print("Запуск сервера...")
    print("Откройте в браузере: http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)

