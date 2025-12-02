"""
Универсальный конвертер документов в HTML и PDF форматы
Поддерживает выборочную конвертацию по фильтрам
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from datetime import datetime

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

try:
    from pypdf import PdfWriter, PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class DocumentConverter:
    """Универсальный конвертер документов в HTML и PDF"""
    
    def __init__(self, documents_dir: str = "documents", 
                 html_dir: str = "html", 
                 pdf_dir: str = "pdf",
                 templates_dir: str = "templates/letterheads"):
        self.documents_dir = Path(documents_dir)
        self.html_dir = Path(html_dir)
        self.pdf_dir = Path(pdf_dir)
        self.templates_dir = Path(templates_dir)
        self.parser = DocumentParser(documents_dir)
        self.html_dir.mkdir(exist_ok=True)
        self.pdf_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    def _fix_broken_lists(self, html_content: str) -> str:
        """
        Исправляет списки, которые не были распознаны markdown2.
        Преобразует структуры вида:
        - <p><strong>Заголовок:</strong>\n- пункт\n- пункт</p>
        - <p><strong>Заголовок:</strong></p>\n- пункт\n- пункт
        в правильные HTML списки.
        """
        import re
        
        # Паттерн 1: Список внутри параграфа с заголовком
        # Ищем <p><strong>Заголовок:</strong>\n- пункт\n- пункт</p>
        pattern1 = r'<p><strong>([^<]+):</strong>\s*\n((?:- [^\n]+\n?)+)</p>'
        
        # Паттерн 2: Список после отдельного параграфа с заголовком
        # Ищем <p><strong>Заголовок:</strong></p>\n- пункт\n- пункт (до следующего блока)
        pattern2 = r'(<p><strong>([^<]+):</strong></p>)\s*\n((?:- [^\n]+\n?)+)(?=\n\n|<p>|<h|<div)'
        
        def replace_with_list1(match):
            header = match.group(1)
            list_items = match.group(2)
            
            # Разбиваем пункты списка
            items = re.findall(r'- ([^\n]+)', list_items)
            
            # Формируем HTML список
            list_html = f'<p><strong>{header}:</strong></p>\n<ul>\n'
            for item in items:
                item_text = item.strip()
                list_html += f'  <li>{item_text}</li>\n'
            list_html += '</ul>'
            
            return list_html
        
        def replace_with_list2(match):
            header_tag = match.group(1)
            header = match.group(2)
            list_items = match.group(3)
            
            # Разбиваем пункты списка
            items = re.findall(r'- ([^\n]+)', list_items)
            
            # Формируем HTML список
            list_html = f'{header_tag}\n<ul>\n'
            for item in items:
                item_text = item.strip()
                list_html += f'  <li>{item_text}</li>\n'
            list_html += '</ul>'
            
            return list_html
        
        # Сначала обрабатываем паттерн 2 (более специфичный)
        html_content = re.sub(pattern2, replace_with_list2, html_content, flags=re.MULTILINE | re.DOTALL)
        
        # Затем обрабатываем паттерн 1
        html_content = re.sub(pattern1, replace_with_list1, html_content, flags=re.MULTILINE)
        
        return html_content
    
    def _process_attachment_links(self, html_content: str, doc_relative_path: str) -> str:
        """
        Обрабатывает ссылки на приложения в HTML
        
        Преобразует относительные пути к приложениям в правильные ссылки
        """
        import re
        from urllib.parse import quote
        
        # Получаем путь к документу без расширения
        doc_path_without_ext = doc_relative_path.replace('.md', '')
        
        # Паттерн для поиска ссылок на приложения
        # Ищем ссылки вида: приложения/файл.png, attachments/файл.jpg и т.д.
        patterns = [
            (r'href=["\'](приложения/[^"\']+)["\']', 'приложения/'),
            (r'href=["\'](attachments/[^"\']+)["\']', 'attachments/'),
            (r'src=["\'](приложения/[^"\']+)["\']', 'приложения/'),
            (r'src=["\'](attachments/[^"\']+)["\']', 'attachments/'),
        ]
        
        # Заменяем относительные пути на абсолютные URL
        for pattern, prefix in patterns:
            def replace_link(match):
                link_path = match.group(1)
                # Кодируем оба пути для URL
                encoded_doc_path = quote(doc_path_without_ext, safe='/')
                encoded_attach_path = quote(link_path, safe='/')
                return match.group(0).replace(link_path, f'/attachment/{encoded_doc_path}/{encoded_attach_path}')
            
            html_content = re.sub(pattern, replace_link, html_content)
        
        return html_content
    
    def _process_document_links_in_markdown(self, markdown_content: str, doc_relative_path: str, metadata: dict) -> str:
        """
        Обрабатывает ссылки на другие документы в Markdown
        
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
                doc_path_found = doc.get('relative_path', '').replace('\\', '/')
                encoded_path = quote(doc_path_found, safe='/')
                return f'[{link_text}](/document/{encoded_path})'
            else:
                # Если документ не найден, оставляем как есть
                return f'[{link_text}](doc:{doc_ref})'
        
        markdown_content = re.sub(pattern, replace_doc_link, markdown_content)
        
        return markdown_content
    
    def _process_document_links(self, html_content: str, doc_relative_path: str, metadata: dict) -> str:
        """
        Обрабатывает ссылки на другие документы в HTML
        
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
                doc_path = doc.get('relative_path', '').replace('\\', '/')
                encoded_path = quote(doc_path, safe='/')
                return f'href="/document/{encoded_path}"'
            else:
                # Если документ не найден, оставляем ссылку как есть, но помечаем как нерабочую
                return f'href="#" class="broken-doc-link" title="Документ не найден: {doc_ref}"'
        
        html_content = re.sub(pattern, replace_doc_link, html_content)
        
        return html_content
    
    def find_letterhead_template(self, document_type: str) -> Optional[Path]:
        """
        Находит шаблон бланка для типа документа
        
        Args:
            document_type: Тип документа (например, 'приказ', 'письмо')
        
        Returns:
            Path к файлу шаблона или None, если не найден
        """
        if not document_type:
            return None
        
        # Ищем шаблон по типу документа
        template_path = self.templates_dir / f"{document_type}.pdf"
        if template_path.exists():
            return template_path
        
        # Если не найден, ищем общий шаблон
        default_template = self.templates_dir / "default.pdf"
        if default_template.exists():
            return default_template
        
        return None
    
    def markdown_to_html(self, markdown_content: str, metadata: dict, 
                        standalone: bool = True, hide_technical: bool = False) -> str:
        """
        Конвертирует Markdown в HTML
        
        Args:
            markdown_content: Содержимое документа в Markdown
            metadata: Метаданные документа
            standalone: Если True, возвращает полный HTML документ, иначе только содержимое
        """
        html_content = markdown2.markdown(
            markdown_content,
            extras=['fenced-code-blocks', 'tables', 'header-ids']
        )
        
        # Исправляем списки, которые не были распознаны markdown2
        # Преобразуем структуры вида <p><strong>Преимущества:</strong>\n- пункт\n- пункт</p> в правильные списки
        html_content = self._fix_broken_lists(html_content)
        
        # Обрабатываем ссылки на приложения
        doc_relative_path = metadata.get('relative_path', '')
        html_content = self._process_attachment_links(html_content, doc_relative_path)
        
        # Обрабатываем ссылки на другие документы
        html_content = self._process_document_links(html_content, doc_relative_path, metadata)
        
        if not standalone:
            return html_content
        
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
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
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
        ul, ol {
            margin-bottom: 10px;
            padding-left: 30px;
        }
        li {
            margin-bottom: 5px;
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
        code {
            background-color: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        pre {
            background-color: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        .footer {
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #000;
            font-size: 10pt;
        }
        @media print {
            body {
                max-width: 100%;
                padding: 0;
            }
        }
        .approval-block {
            text-align: right;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #ddd;
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
    
    {% if metadata and not hide_technical %}
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
    
    {% if metadata.amendment_procedure and not hide_technical %}
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
            content=html_content,
            hide_technical=hide_technical
        )
    
    def generate_html(self, document: dict) -> Optional[Path]:
        """Генерирует HTML для одного документа"""
        try:
            html_content = self.markdown_to_html(
                document['content'],
                document,
                standalone=True
            )
            
            # Определяем путь для HTML
            rel_path = Path(document['relative_path'])
            html_path = self.html_dir / rel_path.with_suffix('.html')
            html_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем HTML
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return html_path
        except Exception as e:
            print(f"✗ Ошибка при генерации HTML для {document.get('file_path', 'unknown')}: {e}")
            return None
    
    def generate_pdf(self, document: dict) -> Optional[Path]:
        """Генерирует PDF для одного документа"""
        try:
            # Проверяем, нужно ли использовать бланк
            print_on_letterhead = document.get('print_on_letterhead', False)
            status = document.get('status', '').lower()
            is_draft = status in ['в разработке', 'черновик', 'разработка']
            
            use_letterhead = print_on_letterhead and not is_draft
            
            # Определяем, скрывать ли технические данные
            hide_technical = use_letterhead
            
            # Генерируем HTML с учетом необходимости скрытия технических данных
            html_content = self.markdown_to_html(
                document['content'],
                document,
                standalone=True,
                hide_technical=hide_technical
            )
            
            # Определяем путь для PDF
            rel_path = Path(document['relative_path'])
            pdf_path = self.pdf_dir / rel_path.with_suffix('.pdf')
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Генерируем PDF контента
            content_pdf_path = pdf_path.parent / f"{pdf_path.stem}_content.pdf"
            
            # Пробуем использовать WeasyPrint (предпочтительно)
            if HAS_WEASYPRINT:
                try:
                    HTML(string=html_content).write_pdf(
                        str(content_pdf_path),
                        presentational_hints=True
                    )
                except Exception as e:
                    print(f"  Предупреждение: WeasyPrint не смог создать PDF: {e}")
                    print("  Пробую использовать pdfkit...")
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
                            pdfkit.from_string(html_content, str(content_pdf_path), options=options)
                        except Exception as e2:
                            if 'No wkhtmltopdf' in str(e2) or 'wkhtmltopdf' in str(e2).lower():
                                raise Exception("wkhtmltopdf не найден. Установите: brew install wkhtmltopdf или используйте WeasyPrint: pip install weasyprint")
                            raise
                    else:
                        raise Exception("Не установлен ни один PDF генератор")
            
            # Пробуем использовать pdfkit (wkhtmltopdf)
            elif HAS_PDFKIT:
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
                    pdfkit.from_string(html_content, str(content_pdf_path), options=options)
                except Exception as e:
                    if 'No wkhtmltopdf' in str(e) or 'wkhtmltopdf' in str(e).lower():
                        raise Exception("wkhtmltopdf не найден. Установите: brew install wkhtmltopdf или используйте WeasyPrint: pip install weasyprint")
                    raise
            else:
                raise Exception("Не установлен ни один PDF генератор. Установите: pip install weasyprint или pip install pdfkit")
            
            # Если нужно использовать бланк, накладываем контент на шаблон
            if use_letterhead and HAS_PYPDF:
                letterhead_template = self.find_letterhead_template(document.get('type', ''))
                if letterhead_template and letterhead_template.exists():
                    try:
                        # Объединяем бланк и контент
                        writer = PdfWriter()
                        
                        # Читаем шаблон бланка
                        letterhead_reader = PdfReader(str(letterhead_template))
                        content_reader = PdfReader(str(content_pdf_path))
                        
                        # Для каждой страницы контента накладываем на бланк
                        for page_num in range(len(content_reader.pages)):
                            # Берем первую страницу бланка (или повторяем, если страниц больше)
                            letterhead_page = letterhead_reader.pages[min(page_num, len(letterhead_reader.pages) - 1)]
                            content_page = content_reader.pages[page_num]
                            
                            # Накладываем контент на бланк
                            letterhead_page.merge_page(content_page)
                            writer.add_page(letterhead_page)
                        
                        # Сохраняем итоговый PDF
                        with open(pdf_path, 'wb') as output_file:
                            writer.write(output_file)
                        
                        # Удаляем временный файл контента
                        content_pdf_path.unlink()
                        
                        return pdf_path
                    except Exception as e:
                        print(f"  Предупреждение: Не удалось наложить бланк: {e}")
                        print(f"  Используется PDF без бланка")
                        # Переименовываем временный файл в итоговый
                        content_pdf_path.rename(pdf_path)
                        return pdf_path
                else:
                    print(f"  Предупреждение: Шаблон бланка не найден для типа '{document.get('type', '')}'")
                    # Переименовываем временный файл в итоговый
                    content_pdf_path.rename(pdf_path)
                    return pdf_path
            else:
                # Просто переименовываем временный файл в итоговый
                if content_pdf_path.exists():
                    content_pdf_path.rename(pdf_path)
                return pdf_path
                
        except Exception as e:
            print(f"✗ Ошибка при генерации PDF для {document.get('file_path', 'unknown')}: {e}")
            return None
    
    def convert_documents(self, 
                         documents: List[Dict],
                         formats: List[str] = ['html', 'pdf'],
                         verbose: bool = True) -> Dict[str, List[Path]]:
        """
        Конвертирует список документов в указанные форматы
        
        Args:
            documents: Список документов для конвертации
            formats: Список форматов ('html', 'pdf')
            verbose: Выводить ли информацию о процессе
        
        Returns:
            Словарь с ключами 'html' и 'pdf', содержащий списки путей к созданным файлам
        """
        results = {'html': [], 'pdf': []}
        
        if verbose:
            print(f"Найдено документов для конвертации: {len(documents)}")
            print(f"Форматы: {', '.join(formats)}")
            print()
        
        for i, doc in enumerate(documents, 1):
            if verbose:
                rel_path = doc.get('relative_path', doc.get('file_path', 'unknown'))
                print(f"[{i}/{len(documents)}] Обработка: {rel_path}")
            
            if 'html' in formats:
                html_path = self.generate_html(doc)
                if html_path:
                    results['html'].append(html_path)
                    if verbose:
                        print(f"  ✓ HTML: {html_path}")
            
            if 'pdf' in formats:
                pdf_path = self.generate_pdf(doc)
                if pdf_path:
                    results['pdf'].append(pdf_path)
                    if verbose:
                        print(f"  ✓ PDF: {pdf_path}")
        
        if verbose:
            print()
            print("=" * 60)
            print(f"Конвертация завершена:")
            if 'html' in formats:
                print(f"  HTML файлов создано: {len(results['html'])}")
            if 'pdf' in formats:
                print(f"  PDF файлов создано: {len(results['pdf'])}")
            print("=" * 60)
        
        return results
    
    def convert_all(self, 
                   formats: List[str] = ['html', 'pdf'],
                   verbose: bool = True) -> Dict[str, List[Path]]:
        """Конвертирует все документы"""
        documents = self.parser.get_all_documents()
        return self.convert_documents(documents, formats, verbose)
    
    def convert_filtered(self,
                        organization: Optional[str] = None,
                        department: Optional[str] = None,
                        doc_type: Optional[str] = None,
                        status: Optional[str] = None,
                        formats: List[str] = ['html', 'pdf'],
                        verbose: bool = True) -> Dict[str, List[Path]]:
        """Конвертирует документы с применением фильтров"""
        documents = self.parser.filter_documents(
            organization=organization,
            department=department,
            doc_type=doc_type,
            status=status
        )
        
        if verbose:
            filters = []
            if organization:
                filters.append(f"организация={organization}")
            if department:
                filters.append(f"отдел={department}")
            if doc_type:
                filters.append(f"тип={doc_type}")
            if status:
                filters.append(f"статус={status}")
            if filters:
                print(f"Применены фильтры: {', '.join(filters)}")
            print()
        
        return self.convert_documents(documents, formats, verbose)


def main():
    """CLI интерфейс для конвертации документов"""
    parser = argparse.ArgumentParser(
        description='Конвертация документов в HTML и PDF форматы'
    )
    
    parser.add_argument(
        '--formats',
        nargs='+',
        choices=['html', 'pdf'],
        default=['html', 'pdf'],
        help='Форматы для конвертации (по умолчанию: html pdf)'
    )
    
    parser.add_argument(
        '--organization',
        type=str,
        help='Фильтр по организации'
    )
    
    parser.add_argument(
        '--department',
        type=str,
        help='Фильтр по отделу'
    )
    
    parser.add_argument(
        '--type',
        type=str,
        dest='doc_type',
        help='Фильтр по типу документа'
    )
    
    parser.add_argument(
        '--status',
        type=str,
        help='Фильтр по статусу документа'
    )
    
    parser.add_argument(
        '--documents-dir',
        type=str,
        default='documents',
        help='Директория с документами (по умолчанию: documents)'
    )
    
    parser.add_argument(
        '--html-dir',
        type=str,
        default='html',
        help='Директория для HTML файлов (по умолчанию: html)'
    )
    
    parser.add_argument(
        '--pdf-dir',
        type=str,
        default='pdf',
        help='Директория для PDF файлов (по умолчанию: pdf)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Минимальный вывод (только ошибки)'
    )
    
    args = parser.parse_args()
    
    # Создаем конвертер
    converter = DocumentConverter(
        documents_dir=args.documents_dir,
        html_dir=args.html_dir,
        pdf_dir=args.pdf_dir
    )
    
    # Определяем, есть ли фильтры
    has_filters = any([
        args.organization,
        args.department,
        args.doc_type,
        args.status
    ])
    
    # Конвертируем
    if has_filters:
        converter.convert_filtered(
            organization=args.organization,
            department=args.department,
            doc_type=args.doc_type,
            status=args.status,
            formats=args.formats,
            verbose=not args.quiet
        )
    else:
        converter.convert_all(
            formats=args.formats,
            verbose=not args.quiet
        )


if __name__ == "__main__":
    main()

