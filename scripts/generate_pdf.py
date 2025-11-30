"""
Генератор PDF из Markdown документов
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import markdown2
from document_parser import DocumentParser
from jinja2 import Template

# Попытка импортировать PDF генераторы
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


class PDFGenerator:
    """Генератор PDF из Markdown документов"""
    
    def __init__(self, documents_dir: str = "documents", pdf_dir: str = "pdf"):
        self.documents_dir = Path(documents_dir)
        self.pdf_dir = Path(pdf_dir)
        self.parser = DocumentParser(documents_dir)
        self.pdf_dir.mkdir(exist_ok=True)
    
    @staticmethod
    def format_date(date_value) -> Optional[str]:
        """
        Форматирует дату в формат дд.ММ.ГГГГ
        
        Поддерживает:
        - строки в форматах YYYY-MM-DD, DD.MM.YYYY и др.
        - объекты datetime.date
        - объекты datetime.datetime
        """
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
    
    def _process_attachment_links(self, html_content: str, doc_relative_path: str) -> str:
        """
        Обрабатывает ссылки на приложения в HTML для PDF
        
        В PDF версии ссылки на приложения преобразуются в локальные пути
        """
        import re
        from pathlib import Path
        
        # Получаем путь к документу
        doc_path = Path(doc_relative_path)
        doc_dir = doc_path.parent
        
        # Паттерн для поиска ссылок на приложения
        patterns = [
            (r'href=["\'](приложения/[^"\']+)["\']', 'приложения/'),
            (r'href=["\'](attachments/[^"\']+)["\']', 'attachments/'),
            (r'src=["\'](приложения/[^"\']+)["\']', 'приложения/'),
            (r'src=["\'](attachments/[^"\']+)["\']', 'attachments/'),
        ]
        
        # Заменяем относительные пути на абсолютные пути к файлам
        for pattern, prefix in patterns:
            def replace_link(match):
                link_path = match.group(1)
                # Создаем абсолютный путь к файлу приложения
                attachment_file = self.documents_dir / doc_dir / link_path
                if attachment_file.exists():
                    return match.group(0).replace(link_path, str(attachment_file))
                return match.group(0)
            
            html_content = re.sub(pattern, replace_link, html_content)
        
        return html_content
    
    def _process_document_links(self, html_content: str, doc_relative_path: str, metadata: dict) -> str:
        """
        Обрабатывает ссылки на другие документы в HTML для PDF
        
        В PDF версии ссылки преобразуются в текстовые ссылки с указанием номера документа
        """
        import re
        
        # Паттерн для поиска ссылок на документы: [текст](doc:ссылка)
        pattern = r'<a\s+href=["\']doc:([^"\']+)["\']>([^<]+)</a>'
        
        def replace_doc_link(match):
            doc_ref = match.group(1)
            link_text = match.group(2)
            
            # Пробуем найти документ
            doc = None
            
            # По номеру
            if 'number' in metadata:
                doc = self.parser.find_document_by_number(
                    doc_ref, 
                    metadata.get('organization')
                )
            
            # По пути
            if not doc:
                doc = self.parser.find_document_by_path(
                    doc_ref,
                    doc_relative_path
                )
            
            if doc:
                doc_number = doc.get('number', '')
                doc_title = doc.get('title', link_text)
                if doc_number:
                    return f'<a href="#doc-{doc_number}" title="{doc_title}">{link_text} (№{doc_number})</a>'
                else:
                    return f'<a href="#doc-{doc_ref}" title="{doc_title}">{link_text}</a>'
            else:
                # Если документ не найден, просто оставляем текст без ссылки
                return f'<span style="color: #999;">{link_text} (документ не найден)</span>'
        
        html_content = re.sub(pattern, replace_doc_link, html_content)
        
        return html_content
    
    def _process_document_links_in_markdown(self, markdown_content: str, doc_relative_path: str, metadata: dict) -> str:
        """
        Обрабатывает ссылки на другие документы в Markdown для PDF
        
        Преобразует ссылки вида [текст](doc:номер) или [текст](doc:путь)
        """
        import re
        
        # Паттерн для поиска ссылок на документы в Markdown: [текст](doc:ссылка)
        pattern = r'\[([^\]]+)\]\(doc:([^\)]+)\)'
        
        def replace_doc_link(match):
            link_text = match.group(1)
            doc_ref = match.group(2).strip()
            
            # Пробуем найти документ
            doc = None
            
            # По номеру
            doc = self.parser.find_document_by_number(
                doc_ref, 
                metadata.get('organization')
            )
            
            # По пути
            if not doc:
                doc = self.parser.find_document_by_path(
                    doc_ref,
                    doc_relative_path
                )
            
            if doc:
                doc_number = doc.get('number', '')
                doc_title = doc.get('title', link_text)
                if doc_number:
                    return f'[{link_text} (№{doc_number})]({doc_title})'
                else:
                    return f'[{link_text}]({doc_title})'
            else:
                # Если документ не найден, просто оставляем текст
                return f'{link_text} (документ не найден)'
        
        markdown_content = re.sub(pattern, replace_doc_link, markdown_content)
        
        return markdown_content
    
    def markdown_to_html(self, markdown_content: str, metadata: dict) -> str:
        """Конвертирует Markdown в HTML с применением стилей"""
        # Обрабатываем ссылки на документы в Markdown перед конвертацией
        doc_relative_path = metadata.get('relative_path', '')
        markdown_content = self._process_document_links_in_markdown(markdown_content, doc_relative_path, metadata)
        
        html_content = markdown2.markdown(
            markdown_content,
            extras=['fenced-code-blocks', 'tables', 'header-ids']
        )
        
        # Обрабатываем ссылки на приложения
        html_content = self._process_attachment_links(html_content, doc_relative_path)
        
        # Обрабатываем ссылки на другие документы в HTML (на случай, если что-то пропустили)
        html_content = self._process_document_links(html_content, doc_relative_path, metadata)
        
        # HTML шаблон для документа
        template = Template("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.5;
            color: #000;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }
        .metadata {
            margin-bottom: 20px;
            font-size: 10pt;
        }
        .metadata table {
            width: 100%;
            border-collapse: collapse;
        }
        .metadata td {
            padding: 5px;
            border: 1px solid #ccc;
        }
        .metadata td:first-child {
            font-weight: bold;
            width: 30%;
        }
        h1 {
            font-size: 16pt;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 15px;
        }
        h2 {
            font-size: 14pt;
            font-weight: bold;
            margin-top: 15px;
            margin-bottom: 10px;
        }
        h3 {
            font-size: 12pt;
            font-weight: bold;
            margin-top: 10px;
            margin-bottom: 8px;
        }
        p {
            margin-bottom: 10px;
            text-align: justify;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        table th, table td {
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
        }
        table th {
            background-color: #f0f0f0;
            font-weight: bold;
        }
        .footer {
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #000;
            font-size: 10pt;
        }
        .approval-block {
            text-align: right;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #000;
            font-size: 11pt;
        }
        .approval-block .approval-title {
            font-weight: bold;
            margin-bottom: 15px;
            font-size: 12pt;
        }
        .approval-block .approval-content {
            line-height: 1.8;
        }
    </style>
</head>
<body>
    {% if metadata.approval_block %}
    <div class="approval-block">
        <div class="approval-title">УТВЕРЖДАЮ</div>
        <div class="approval-content">
            {% for line in metadata.approval_block.split('\n') %}
            {{ line }}<br>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    
    <div class="header">
        <h1>{{ title }}</h1>
    </div>
    
    {% if metadata %}
    <div class="metadata">
        <table>
            {% if metadata.organization %}
            <tr>
                <td>Организация:</td>
                <td>{{ metadata.organization }}</td>
            </tr>
            {% endif %}
            {% if metadata.department %}
            <tr>
                <td>Отдел:</td>
                <td>{{ metadata.department }}</td>
            </tr>
            {% endif %}
            {% if metadata.type %}
            <tr>
                <td>Тип документа:</td>
                <td>{{ metadata.type }}</td>
            </tr>
            {% endif %}
            {% if metadata.number %}
            <tr>
                <td>Номер:</td>
                <td>{{ metadata.number }}</td>
            </tr>
            {% endif %}
            {% if metadata.date %}
            <tr>
                <td>Дата:</td>
                <td>{{ metadata.date }}</td>
            </tr>
            {% endif %}
            {% if metadata.status %}
            <tr>
                <td>Статус:</td>
                <td>{{ metadata.status }}</td>
            </tr>
            {% endif %}
            {% if metadata.approved_date %}
            <tr>
                <td>Дата подписания (утверждения):</td>
                <td>{{ metadata.approved_date }}</td>
            </tr>
            {% endif %}
            {% if metadata.effective_date %}
            <tr>
                <td>Дата ввода в действие:</td>
                <td>{{ metadata.effective_date }}</td>
            </tr>
            {% endif %}
            {% if metadata.expiry_date %}
            <tr>
                <td>Дата окончания действия:</td>
                <td>{{ metadata.expiry_date }}</td>
            </tr>
            {% elif metadata.expiry_type %}
            <tr>
                <td>Срок действия:</td>
                <td>{{ metadata.expiry_type }}</td>
            </tr>
            {% endif %}
        </table>
    </div>
    {% endif %}
    
    {% if metadata.amendment_procedure %}
    <div class="amendment-procedure" style="margin-bottom: 20px; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #0066cc;">
        <h3 style="margin-top: 0; color: #0066cc;">Порядок внесения изменений</h3>
        <p style="margin-bottom: 0;">{{ metadata.amendment_procedure }}</p>
    </div>
    {% endif %}
    
    <div class="content">
        {{ content|safe }}
    </div>
    
    <div class="footer">
        <p>Страница <span class="page"></span></p>
    </div>
</body>
</html>
        """)
        
        title = metadata.get('title', metadata.get('number', 'Документ'))
        
        # Форматируем даты в формат дд.ММ.ГГГГ
        formatted_metadata = metadata.copy()
        if 'approved_date' in formatted_metadata:
            formatted_metadata['approved_date'] = self.format_date(formatted_metadata['approved_date'])
        if 'effective_date' in formatted_metadata:
            formatted_metadata['effective_date'] = self.format_date(formatted_metadata['effective_date'])
        if 'expiry_date' in formatted_metadata:
            formatted_metadata['expiry_date'] = self.format_date(formatted_metadata['expiry_date'])
        if 'date' in formatted_metadata:
            formatted_metadata['date'] = self.format_date(formatted_metadata['date'])
        
        return template.render(
            title=title,
            metadata=formatted_metadata,
            content=html_content
        )
    
    def generate_pdf(self, document: dict) -> Path:
        """Генерирует PDF для одного документа"""
        html_content = self.markdown_to_html(
            document['content'],
            document
        )
        
        # Определяем путь для PDF
        rel_path = Path(document['relative_path'])
        pdf_path = self.pdf_dir / rel_path.with_suffix('.pdf')
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Генерируем PDF
        try:
            # Пробуем использовать WeasyPrint (предпочтительно)
            if HAS_WEASYPRINT:
                try:
                    HTML(string=html_content).write_pdf(
                        pdf_path,
                        presentational_hints=True
                    )
                    print(f"✓ Сгенерирован PDF: {pdf_path}")
                    return pdf_path
                except Exception as e:
                    print(f"  Предупреждение: WeasyPrint не смог создать PDF: {e}")
                    print("  Пробую использовать pdfkit...")
            
            # Пробуем использовать pdfkit (wkhtmltopdf)
            if HAS_PDFKIT:
                try:
                    options = {
                        'page-size': 'A4',
                        'margin-top': '2cm',
                        'margin-right': '2cm',
                        'margin-bottom': '2cm',
                        'margin-left': '2cm',
                        'encoding': "UTF-8",
                        'no-outline': None,
                        'enable-local-file-access': None
                    }
                    pdfkit.from_string(html_content, str(pdf_path), options=options)
                    print(f"✓ Сгенерирован PDF: {pdf_path}")
                    return pdf_path
                except Exception as e:
                    if 'No wkhtmltopdf' in str(e) or 'wkhtmltopdf' in str(e).lower():
                        raise Exception("wkhtmltopdf не найден. Установите: brew install wkhtmltopdf или используйте WeasyPrint: pip install weasyprint")
                    raise
            else:
                raise Exception("Не установлен ни один PDF генератор. Установите: pip install weasyprint или pip install pdfkit")
                
        except Exception as e:
            print(f"✗ Ошибка при генерации PDF для {document['file_path']}: {e}")
            return None
    
    def generate_all_pdfs(self):
        """Генерирует PDF для всех документов"""
        documents = self.parser.get_all_documents()
        print(f"Найдено документов: {len(documents)}")
        
        for doc in documents:
            self.generate_pdf(doc)
        
        print(f"\nГенерация завершена. PDF файлы сохранены в {self.pdf_dir}")


if __name__ == "__main__":
    # Используем новый конвертер для обратной совместимости
    from document_converter import DocumentConverter
    converter = DocumentConverter()
    converter.convert_all(formats=['pdf'], verbose=True)

