"""
Тесты для парсера документов
"""
import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Добавляем путь к скриптам
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from document_parser import DocumentParser


class TestDocumentParser(unittest.TestCase):
    """Тесты для DocumentParser"""
    
    def setUp(self):
        """Создание временной директории для тестов"""
        self.test_dir = tempfile.mkdtemp()
        self.parser = DocumentParser(self.test_dir)
        
        # Создаем тестовую структуру
        self.doc_dir = Path(self.test_dir)
        self.doc_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Удаление временной директории"""
        shutil.rmtree(self.test_dir)
    
    def test_parse_simple_document(self):
        """Тест парсинга простого документа"""
        doc_content = """---
type: приказ
organization: Тестовая организация
department: Тестовый отдел
number: ТЕСТ-001
date: 2024-01-01
title: Тестовый документ
status: действующий
---

# Заголовок

Содержимое документа.
"""
        doc_file = self.doc_dir / "test.md"
        doc_file.write_text(doc_content, encoding='utf-8')
        
        result = self.parser.parse_document(doc_file)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'приказ')
        self.assertEqual(result['organization'], 'Тестовая организация')
        self.assertEqual(result['department'], 'Тестовый отдел')
        self.assertEqual(result['number'], 'ТЕСТ-001')
        self.assertIn('Содержимое документа', result['content'])
    
    def test_parse_document_without_yaml(self):
        """Тест парсинга документа без YAML front matter"""
        doc_content = """# Простой документ

Содержимое без метаданных.
"""
        doc_file = self.doc_dir / "simple.md"
        doc_file.write_text(doc_content, encoding='utf-8')
        
        result = self.parser.parse_document(doc_file)
        
        self.assertIsNotNone(result)
        self.assertIn('Простой документ', result['content'])
    
    def test_get_all_documents(self):
        """Тест получения всех документов"""
        # Создаем несколько документов
        for i in range(3):
            doc_file = self.doc_dir / f"doc_{i}.md"
            doc_file.write_text(f"# Документ {i}\n\nСодержимое.", encoding='utf-8')
        
        documents = self.parser.get_all_documents()
        
        self.assertEqual(len(documents), 3)
    
    def test_filter_documents(self):
        """Тест фильтрации документов"""
        # Создаем документы с разными метаданными
        doc1 = self.doc_dir / "doc1.md"
        doc1.write_text("""---
type: приказ
organization: Орг1
department: Отдел1
---
# Документ 1
""", encoding='utf-8')
        
        doc2 = self.doc_dir / "doc2.md"
        doc2.write_text("""---
type: распоряжение
organization: Орг1
department: Отдел2
---
# Документ 2
""", encoding='utf-8')
        
        # Фильтр по типу
        filtered = self.parser.filter_documents(doc_type='приказ')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['type'], 'приказ')
        
        # Фильтр по отделу
        filtered = self.parser.filter_documents(department='Отдел1')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['department'], 'Отдел1')


if __name__ == '__main__':
    unittest.main()

