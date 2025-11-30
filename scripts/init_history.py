"""
Скрипт для инициализации истории существующих документов
"""
import os
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_tracker import VersionTracker


def main():
    """Инициализация истории для всех существующих документов"""
    base_dir = Path(__file__).parent.parent
    documents_dir = base_dir / "documents"
    history_dir = base_dir / "version_history"
    
    if not documents_dir.exists():
        print(f"Директория документов не найдена: {documents_dir}")
        return
    
    tracker = VersionTracker(str(documents_dir), str(history_dir))
    
    print("Инициализация истории изменений для существующих документов...")
    print(f"Директория документов: {documents_dir}")
    print(f"Директория истории: {history_dir}\n")
    
    # Получаем все документы
    documents = []
    for md_file in documents_dir.rglob('*.md'):
        documents.append(md_file)
    
    if not documents:
        print("Документы не найдены.")
        return
    
    print(f"Найдено документов: {len(documents)}\n")
    
    # Запрашиваем автора
    author = input("Введите имя автора для инициализации (или нажмите Enter для 'system'): ").strip()
    if not author:
        author = "system"
    
    comment = input("Введите комментарий для инициализации (или нажмите Enter): ").strip()
    if not comment:
        comment = "Инициализация истории документов"
    
    # Отслеживаем все документы
    tracked = 0
    for doc_file in documents:
        try:
            change = tracker.track_change(doc_file, author, comment)
            if change:
                print(f"✓ {doc_file.relative_to(documents_dir)} - версия {change['version']}")
                tracked += 1
        except Exception as e:
            print(f"✗ Ошибка при обработке {doc_file.relative_to(documents_dir)}: {e}")
    
    print(f"\nИнициализация завершена. Обработано документов: {tracked}/{len(documents)}")


if __name__ == "__main__":
    main()

