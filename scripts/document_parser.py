"""
Парсер документов из Markdown с YAML front matter
"""
import os
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DocumentParser:
    """Парсер документов в формате Markdown с метаданными"""
    
    def __init__(self, documents_dir: str = "documents"):
        self.documents_dir = Path(documents_dir)
    
    def parse_document(self, file_path: Path) -> Optional[Dict]:
        """Парсит документ и возвращает метаданные и содержимое"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Разделяем YAML front matter и Markdown
            yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
            
            if yaml_match:
                yaml_content = yaml_match.group(1)
                markdown_content = yaml_match.group(2)
                metadata = yaml.safe_load(yaml_content)
            else:
                metadata = {}
                markdown_content = content
            
            # Добавляем путь к файлу
            metadata['file_path'] = str(file_path)
            metadata['relative_path'] = str(file_path.relative_to(self.documents_dir))
            metadata['content'] = markdown_content
            
            # Извлекаем организацию и отдел из пути
            parts = file_path.relative_to(self.documents_dir).parts
            if len(parts) >= 2:
                metadata['organization'] = metadata.get('organization', parts[0])
                metadata['department'] = metadata.get('department', parts[1])
            
            # Ищем приложения к документу
            attachments = self._find_attachments(file_path)
            if attachments:
                metadata['attachments'] = attachments
            
            # Извлекаем блок "УТВЕРЖДАЮ" из содержимого
            approval_block, cleaned_content = self._extract_approval_block(markdown_content)
            if approval_block:
                metadata['approval_block'] = approval_block
                metadata['content'] = cleaned_content
            
            return metadata
        except Exception as e:
            print(f"Ошибка при парсинге {file_path}: {e}")
            return None
    
    def _extract_approval_block(self, content: str) -> Tuple[Optional[str], str]:
        """
        Извлекает блок "УТВЕРЖДАЮ" из содержимого документа
        
        Returns:
            (approval_block, cleaned_content) - блок утверждения и очищенное содержимое
        """
        import re
        
        # Ищем блок в начале документа
        # Паттерн: # УТВЕРЖДАЮ или **УТВЕРЖДАЮ** или УТВЕРЖДАЮ, затем текст до следующего заголовка
        start_match = re.search(
            r'^(?:#\s*|\*\*)?УТВЕРЖДАЮ(?:\*\*)?\s*\n\n(.*?)(?=\n\n#\s+[^У])',
            content,
            re.DOTALL | re.MULTILINE | re.IGNORECASE
        )
        
        if start_match:
            approval_block = start_match.group(1).strip()
            # Убираем блок из начала (включая заголовок УТВЕРЖДАЮ)
            cleaned_content = re.sub(
                r'^(?:#\s*|\*\*)?УТВЕРЖДАЮ(?:\*\*)?\s*\n\n.*?(?=\n\n#\s+[^У])',
                '',
                content,
                flags=re.DOTALL | re.MULTILINE | re.IGNORECASE
            )
            return approval_block, cleaned_content.strip()
        
        # Ищем блок в конце документа (после ---)
        end_match = re.search(
            r'\n---\s*\n\n(?:#\s*|\*\*)?УТВЕРЖДАЮ(?:\*\*)?\s*\n\n(.*?)(?:\n---|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        
        if end_match:
            approval_block = end_match.group(1).strip()
            # Убираем весь блок из конца (включая --- и заголовок УТВЕРЖДАЮ)
            cleaned_content = re.sub(
                r'\n---\s*\n\n(?:#\s*|\*\*)?УТВЕРЖДАЮ(?:\*\*)?\s*\n\n.*?(?:\n---|\Z)',
                '',
                content,
                flags=re.DOTALL | re.IGNORECASE
            )
            # Убираем оставшийся --- если есть
            cleaned_content = re.sub(r'\n---\s*\n\s*$', '', cleaned_content)
            return approval_block, cleaned_content.strip()
        
        return None, content
    
    def _find_attachments(self, doc_path: Path) -> List[Dict]:
        """
        Находит приложения к документу
        
        Ищет файлы в директориях:
        - приложения/ (рядом с документом)
        - attachments/ (рядом с документом)
        - {имя_документа}_приложения/ (рядом с документом)
        
        Returns:
            Список словарей с информацией о приложениях
        """
        attachments = []
        doc_dir = doc_path.parent
        doc_name = doc_path.stem
        
        # Возможные имена директорий с приложениями
        attachment_dir_names = [
            'приложения',
            'attachments',
            f'{doc_name}_приложения',
            f'{doc_name}_attachments'
        ]
        
        # Поддерживаемые форматы файлов
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}
        table_extensions = {'.xlsx', '.xls', '.csv', '.ods'}
        other_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
        all_extensions = image_extensions | table_extensions | other_extensions
        
        for dir_name in attachment_dir_names:
            attachment_dir = doc_dir / dir_name
            if attachment_dir.exists() and attachment_dir.is_dir():
                for file_path in attachment_dir.rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in all_extensions:
                        rel_path = file_path.relative_to(doc_dir)
                        file_type = 'image' if file_path.suffix.lower() in image_extensions else \
                                   'table' if file_path.suffix.lower() in table_extensions else \
                                   'other'
                        
                        attachments.append({
                            'name': file_path.name,
                            'path': str(rel_path),
                            'relative_path': str(rel_path),
                            'type': file_type,
                            'size': file_path.stat().st_size,
                            'extension': file_path.suffix.lower()
                        })
                break  # Используем первую найденную директорию
        
        return sorted(attachments, key=lambda x: x['name'])
    
    def get_all_documents(self) -> List[Dict]:
        """Получает все документы из директории"""
        documents = []
        
        if not self.documents_dir.exists():
            return documents
        
        for md_file in self.documents_dir.rglob('*.md'):
            doc = self.parse_document(md_file)
            if doc:
                documents.append(doc)
        
        return documents
    
    def get_organizations(self) -> List[str]:
        """Получает список всех организаций"""
        orgs = set()
        for doc in self.get_all_documents():
            if 'organization' in doc:
                orgs.add(doc['organization'])
        return sorted(list(orgs))
    
    def get_departments(self, organization: Optional[str] = None) -> List[str]:
        """Получает список отделов (опционально для конкретной организации)"""
        depts = set()
        for doc in self.get_all_documents():
            if 'department' in doc:
                if organization is None or doc.get('organization') == organization:
                    depts.add(doc['department'])
        return sorted(list(depts))
    
    def get_document_types(self) -> List[str]:
        """Получает список типов документов"""
        types = set()
        for doc in self.get_all_documents():
            if 'type' in doc:
                types.add(doc['type'])
        return sorted(list(types))
    
    def filter_documents(self, organization: Optional[str] = None,
                        department: Optional[str] = None,
                        doc_type: Optional[str] = None,
                        status: Optional[str] = None) -> List[Dict]:
        """Фильтрует документы по критериям"""
        documents = self.get_all_documents()
        
        filtered = []
        for doc in documents:
            if organization and doc.get('organization') != organization:
                continue
            if department and doc.get('department') != department:
                continue
            if doc_type and doc.get('type') != doc_type:
                continue
            if status and doc.get('status') != status:
                continue
            filtered.append(doc)
        
        return filtered
    
    def find_document_by_number(self, number: str, 
                                organization: Optional[str] = None) -> Optional[Dict]:
        """
        Находит документ по номеру
        
        Args:
            number: Номер документа (например, "ПОЛ-001")
            organization: Опционально, ограничить поиск организацией
        
        Returns:
            Словарь с метаданными документа или None
        """
        documents = self.get_all_documents()
        
        for doc in documents:
            if doc.get('number') == number:
                if organization is None or doc.get('organization') == organization:
                    return doc
        
        return None
    
    def find_document_by_path(self, path: str, 
                             current_doc_path: Optional[str] = None) -> Optional[Dict]:
        """
        Находит документ по пути
        
        Поддерживает:
        - Относительные пути: "положения/положение.md"
        - Абсолютные пути: "ООО ФК РАНА/Отдел/положения/положение.md"
        - Пути относительно текущего документа
        
        Args:
            path: Путь к документу
            current_doc_path: Путь текущего документа (для разрешения относительных путей)
        
        Returns:
            Словарь с метаданными документа или None
        """
        # Если путь уже содержит расширение .md, используем как есть
        if not path.endswith('.md'):
            path = f"{path}.md"
        
        # Пробуем как абсолютный путь
        doc_file = self.documents_dir / path
        if doc_file.exists() and doc_file.is_file():
            return self.parse_document(doc_file)
        
        # Если указан текущий документ, пробуем относительный путь
        if current_doc_path:
            current_doc = Path(current_doc_path)
            current_dir = current_doc.parent
            
            # Относительный путь от текущего документа
            relative_file = current_dir / path
            if relative_file.exists() and relative_file.is_file():
                return self.parse_document(relative_file)
            
            # Относительный путь от директории текущего документа
            relative_file = self.documents_dir / current_dir / path
            if relative_file.exists() and relative_file.is_file():
                return self.parse_document(relative_file)
        
        return None
    
    def resolve_document_link(self, link: str, 
                             current_doc_path: Optional[str] = None,
                             current_org: Optional[str] = None) -> Optional[str]:
        """
        Разрешает ссылку на документ в относительный путь для URL
        
        Args:
            link: Ссылка в формате doc:номер или doc:путь
            current_doc_path: Путь текущего документа
            current_org: Организация текущего документа
        
        Returns:
            Относительный путь к документу для использования в URL или None
        """
        if not link.startswith('doc:'):
            return None
        
        doc_ref = link[4:].strip()  # Убираем префикс "doc:"
        
        # Пробуем найти по номеру
        doc = self.find_document_by_number(doc_ref, current_org)
        if doc:
            return doc.get('relative_path', '').replace('\\', '/')
        
        # Пробуем найти по пути
        doc = self.find_document_by_path(doc_ref, current_doc_path)
        if doc:
            return doc.get('relative_path', '').replace('\\', '/')
        
        return None

