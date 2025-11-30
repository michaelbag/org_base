"""
Система отслеживания изменений документов
"""
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import shutil
from document_parser import DocumentParser


class VersionTracker:
    """Отслеживание версий и изменений документов"""
    
    def __init__(self, documents_dir: str = "documents", history_dir: str = "version_history"):
        self.documents_dir = Path(documents_dir)
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        self.parser = DocumentParser(documents_dir)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Вычисляет хеш файла для определения изменений"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _get_history_file(self, doc_path: Path) -> Path:
        """Возвращает путь к файлу истории для документа"""
        # Создаем уникальный путь на основе относительного пути документа
        rel_path = doc_path.relative_to(self.documents_dir)
        history_path = self.history_dir / rel_path.with_suffix('.json')
        history_path.parent.mkdir(parents=True, exist_ok=True)
        return history_path
    
    def _load_history(self, history_file: Path) -> List[Dict]:
        """Загружает историю изменений"""
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_history(self, history_file: Path, history: List[Dict]):
        """Сохраняет историю изменений"""
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def _save_version(self, doc_path: Path, version_info: Dict) -> Path:
        """Сохраняет версию документа"""
        rel_path = doc_path.relative_to(self.documents_dir)
        version_dir = self.history_dir / "versions" / rel_path.parent
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя файла версии: {original_name}.v{version_number}.md
        version_file = version_dir / f"{doc_path.stem}.v{version_info['version']}.md"
        
        # Копируем содержимое документа
        shutil.copy2(doc_path, version_file)
        
        return version_file
    
    def track_change(self, doc_path: Path, author: str, comment: Optional[str] = None) -> Dict:
        """Отслеживает изменение документа"""
        if not doc_path.exists():
            return None
        
        history_file = self._get_history_file(doc_path)
        history = self._load_history(history_file)
        
        # Вычисляем хеш текущей версии
        current_hash = self._get_file_hash(doc_path)
        
        # Проверяем, было ли изменение
        if history and history[-1].get('hash') == current_hash:
            return history[-1]  # Документ не изменился
        
        # Парсим документ для получения метаданных
        doc_metadata = self.parser.parse_document(doc_path)
        
        # Создаем запись об изменении
        version_number = len(history) + 1
        change_record = {
            'version': version_number,
            'timestamp': datetime.now().isoformat(),
            'author': author,
            'comment': comment or '',
            'hash': current_hash,
            'file_path': str(doc_path.relative_to(self.documents_dir)),
            'metadata': {
                'type': doc_metadata.get('type'),
                'organization': doc_metadata.get('organization'),
                'department': doc_metadata.get('department'),
                'number': doc_metadata.get('number'),
                'title': doc_metadata.get('title'),
                'date': doc_metadata.get('date'),
                'status': doc_metadata.get('status'),
            } if doc_metadata else {}
        }
        
        # Сохраняем версию файла
        version_file = self._save_version(doc_path, change_record)
        change_record['version_file'] = str(version_file.relative_to(self.history_dir))
        
        # Добавляем в историю
        history.append(change_record)
        self._save_history(history_file, history)
        
        return change_record
    
    def get_history(self, doc_path: Path) -> List[Dict]:
        """Получает историю изменений документа"""
        history_file = self._get_history_file(doc_path)
        return self._load_history(history_file)
    
    def get_document_version(self, doc_path: Path, version: int) -> Optional[Dict]:
        """Получает конкретную версию документа"""
        history = self.get_history(doc_path)
        
        for record in history:
            if record['version'] == version:
                version_file = self.history_dir / record['version_file']
                if version_file.exists():
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    record['content'] = content
                    return record
        return None
    
    def compare_versions(self, doc_path: Path, version1: int, version2: int) -> Dict:
        """Сравнивает две версии документа"""
        v1 = self.get_document_version(doc_path, version1)
        v2 = self.get_document_version(doc_path, version2)
        
        if not v1 or not v2:
            return None
        
        # Простое сравнение (можно улучшить с помощью diff алгоритма)
        return {
            'version1': v1,
            'version2': v2,
            'changed': v1['hash'] != v2['hash']
        }
    
    def track_all_documents(self, author: str = "system"):
        """Отслеживает все документы в директории"""
        documents = []
        for md_file in self.documents_dir.rglob('*.md'):
            change = self.track_change(md_file, author, "Автоматическое отслеживание")
            if change:
                documents.append(change)
        return documents

