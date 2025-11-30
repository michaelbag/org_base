"""
Тесты для системы версионирования
"""
import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import os
import json

# Добавляем путь к скриптам
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from version_tracker import VersionTracker


class TestVersionTracker(unittest.TestCase):
    """Тесты для VersionTracker"""
    
    def setUp(self):
        """Создание временных директорий для тестов"""
        self.test_dir = tempfile.mkdtemp()
        self.history_dir = tempfile.mkdtemp()
        
        self.doc_dir = Path(self.test_dir)
        self.doc_dir.mkdir(exist_ok=True)
        
        self.tracker = VersionTracker(self.test_dir, self.history_dir)
    
    def tearDown(self):
        """Удаление временных директорий"""
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.history_dir)
    
    def test_track_change(self):
        """Тест отслеживания изменения"""
        doc_file = self.doc_dir / "test.md"
        doc_file.write_text("# Тест\n\nСодержимое.", encoding='utf-8')
        
        change = self.tracker.track_change(doc_file, "test_user", "Тестовое изменение")
        
        self.assertIsNotNone(change)
        self.assertEqual(change['version'], 1)
        self.assertEqual(change['author'], "test_user")
        self.assertEqual(change['comment'], "Тестовое изменение")
        self.assertIn('timestamp', change)
        self.assertIn('hash', change)
    
    def test_get_history(self):
        """Тест получения истории"""
        doc_file = self.doc_dir / "test.md"
        doc_file.write_text("# Тест\n\nВерсия 1.", encoding='utf-8')
        
        # Первое изменение
        self.tracker.track_change(doc_file, "user1", "Первая версия")
        
        # Второе изменение
        doc_file.write_text("# Тест\n\nВерсия 2.", encoding='utf-8')
        self.tracker.track_change(doc_file, "user2", "Вторая версия")
        
        history = self.tracker.get_history(doc_file)
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['version'], 1)
        self.assertEqual(history[1]['version'], 2)
        self.assertEqual(history[0]['author'], "user1")
        self.assertEqual(history[1]['author'], "user2")
    
    def test_get_document_version(self):
        """Тест получения конкретной версии"""
        doc_file = self.doc_dir / "test.md"
        doc_file.write_text("# Тест\n\nВерсия 1.", encoding='utf-8')
        
        self.tracker.track_change(doc_file, "user1")
        
        doc_file.write_text("# Тест\n\nВерсия 2.", encoding='utf-8')
        self.tracker.track_change(doc_file, "user2")
        
        version = self.tracker.get_document_version(doc_file, 1)
        
        self.assertIsNotNone(version)
        self.assertEqual(version['version'], 1)
        self.assertIn('Версия 1', version['content'])
    
    def test_no_duplicate_tracking(self):
        """Тест что одинаковые изменения не отслеживаются дважды"""
        doc_file = self.doc_dir / "test.md"
        doc_file.write_text("# Тест\n\nСодержимое.", encoding='utf-8')
        
        change1 = self.tracker.track_change(doc_file, "user1")
        change2 = self.tracker.track_change(doc_file, "user1")
        
        # Второй вызов должен вернуть тот же результат, так как файл не изменился
        self.assertEqual(change1['hash'], change2['hash'])
        
        history = self.tracker.get_history(doc_file)
        # Должна быть только одна запись
        self.assertEqual(len(history), 1)


if __name__ == '__main__':
    unittest.main()

