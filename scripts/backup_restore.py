"""
Модуль резервного копирования и восстановления рабочих данных
"""
import os
import sys
import json
import tarfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import argparse
from io import BytesIO

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class BackupRestore:
    """Класс для резервного копирования и восстановления рабочих данных"""
    
    # Директории, которые считаются рабочими данными
    WORKING_DIRECTORIES = [
        'documents',      # Исходные документы
        'version_history',  # История изменений
        'html',          # Сгенерированные HTML (опционально)
        'pdf',           # Сгенерированные PDF (опционально)
        'config',        # Конфигурационные файлы
    ]
    
    # Файлы, которые нужно включить в резервную копию
    WORKING_FILES = [
        'requirements.txt',
        'README.md',
    ]
    
    def __init__(self, base_dir: str = ".", backup_dir: str = "backups"):
        """
        Инициализация
        
        Args:
            base_dir: Базовая директория проекта
            backup_dir: Директория для хранения резервных копий
        """
        self.base_dir = Path(base_dir).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, 
                     include_html: bool = True,
                     include_pdf: bool = True,
                     comment: Optional[str] = None) -> Path:
        """
        Создает резервную копию всех рабочих данных
        
        Args:
            include_html: Включать ли HTML файлы
            include_pdf: Включать ли PDF файлы
            comment: Комментарий к резервной копии
        
        Returns:
            Path к созданному архиву
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        print(f"Создание резервной копии...")
        print(f"Базовая директория: {self.base_dir}")
        print(f"Файл резервной копии: {backup_path}")
        
        # Метаданные резервной копии
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'base_dir': str(self.base_dir),
            'comment': comment,
            'included_directories': [],
            'included_files': [],
        }
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Добавляем директории
                for dir_name in self.WORKING_DIRECTORIES:
                    dir_path = self.base_dir / dir_name
                    
                    # Пропускаем HTML и PDF если не нужно включать
                    if dir_name == 'html' and not include_html:
                        continue
                    if dir_name == 'pdf' and not include_pdf:
                        continue
                    
                    if dir_path.exists() and dir_path.is_dir():
                        print(f"  Добавление директории: {dir_name}/")
                        tar.add(dir_path, arcname=dir_name, recursive=True)
                        metadata['included_directories'].append(dir_name)
                
                # Добавляем файлы
                for file_name in self.WORKING_FILES:
                    file_path = self.base_dir / file_name
                    if file_path.exists() and file_path.is_file():
                        print(f"  Добавление файла: {file_name}")
                        tar.add(file_path, arcname=file_name)
                        metadata['included_files'].append(file_name)
                
                # Добавляем метаданные в архив
                metadata_str = json.dumps(metadata, ensure_ascii=False, indent=2)
                metadata_bytes = metadata_str.encode('utf-8')
                metadata_info = tarfile.TarInfo(name='backup_metadata.json')
                metadata_info.size = len(metadata_bytes)
                tar.addfile(metadata_info, fileobj=BytesIO(metadata_bytes))
            
            # Сохраняем метаданные отдельно для быстрого доступа
            metadata_path = self.backup_dir / f"backup_{timestamp}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            backup_size = backup_path.stat().st_size / (1024 * 1024)  # MB
            print(f"\n✓ Резервная копия успешно создана!")
            print(f"  Размер: {backup_size:.2f} MB")
            print(f"  Путь: {backup_path}")
            if comment:
                print(f"  Комментарий: {comment}")
            
            return backup_path
            
        except Exception as e:
            print(f"✗ Ошибка при создании резервной копии: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise
    
    def list_backups(self) -> List[Dict]:
        """
        Возвращает список доступных резервных копий
        
        Returns:
            Список словарей с информацией о резервных копиях
        """
        backups = []
        
        for backup_file in self.backup_dir.glob('backup_*.tar.gz'):
            try:
                # Пытаемся загрузить метаданные
                # backup_file.stem = "backup_20251130_083311" (без .tar.gz)
                timestamp = backup_file.stem.replace('backup_', '').replace('.tar', '')
                metadata_file = self.backup_dir / f"backup_{timestamp}_metadata.json"
                
                metadata = {}
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                
                backup_info = {
                    'path': backup_file,
                    'filename': backup_file.name,
                    'size': backup_file.stat().st_size,
                    'timestamp': timestamp,
                    'metadata': metadata,
                }
                backups.append(backup_info)
            except Exception as e:
                print(f"Предупреждение: не удалось прочитать информацию о {backup_file.name}: {e}")
        
        # Сортируем по дате (новые первыми)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups
    
    def get_backup_metadata(self, backup_path: Path) -> Optional[Dict]:
        """
        Получает метаданные резервной копии
        
        Args:
            backup_path: Путь к архиву резервной копии
        
        Returns:
            Словарь с метаданными или None
        """
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                try:
                    metadata_file = tar.extractfile('backup_metadata.json')
                    if metadata_file:
                        metadata = json.loads(metadata_file.read().decode('utf-8'))
                        return metadata
                except KeyError:
                    pass
            
            # Пробуем найти отдельный файл метаданных
            timestamp = backup_path.stem.replace('backup_', '')
            metadata_file = self.backup_dir / f"backup_{timestamp}_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка при чтении метаданных: {e}")
        
        return None
    
    def _validate_backup(self, backup_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Проверяет целостность резервной копии
        
        Returns:
            (is_valid, error_message)
        """
        if not backup_path.exists():
            return False, f"Резервная копия не найдена: {backup_path}"
        
        if not backup_path.is_file():
            return False, f"Указанный путь не является файлом: {backup_path}"
        
        # Проверяем, что это tar.gz архив
        if not backup_path.suffixes == ['.tar', '.gz']:
            return False, f"Файл не является tar.gz архивом: {backup_path}"
        
        # Проверяем целостность архива
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                # Проверяем наличие критических директорий
                members = tar.getnames()
                if 'documents' not in members and 'documents/' not in [m.split('/')[0] for m in members]:
                    return False, "Архив не содержит директорию 'documents' - критическая ошибка!"
                
                # Проверяем наличие метаданных
                if 'backup_metadata.json' not in members:
                    print("  Предупреждение: метаданные не найдены в архиве")
        except tarfile.TarError as e:
            return False, f"Ошибка при проверке архива: {e}"
        except Exception as e:
            return False, f"Неожиданная ошибка при проверке архива: {e}"
        
        return True, None
    
    def restore_backup(self, 
                      backup_path: Path,
                      replace_existing: bool = True,
                      restore_html: bool = True,
                      restore_pdf: bool = True,
                      create_backup_before: bool = True) -> bool:
        """
        Восстанавливает рабочие данные из резервной копии
        
        Args:
            backup_path: Путь к архиву резервной копии
            replace_existing: Заменять ли существующие данные
            restore_html: Восстанавливать ли HTML файлы
            restore_pdf: Восстанавливать ли PDF файлы
            create_backup_before: Создавать ли резервную копию перед восстановлением
        
        Returns:
            True если восстановление успешно, False иначе
        """
        # Проверка целостности архива
        is_valid, error_msg = self._validate_backup(backup_path)
        if not is_valid:
            print(f"✗ {error_msg}")
            return False
        
        # Получаем метаданные
        metadata = self.get_backup_metadata(backup_path)
        if metadata:
            print(f"Информация о резервной копии:")
            print(f"  Дата создания: {metadata.get('timestamp', 'неизвестно')}")
            if metadata.get('comment'):
                print(f"  Комментарий: {metadata['comment']}")
            print(f"  Включенные директории: {', '.join(metadata.get('included_directories', []))}")
        
        # Проверяем существующие данные
        existing_dirs = []
        for dir_name in self.WORKING_DIRECTORIES:
            dir_path = self.base_dir / dir_name
            if dir_path.exists() and any(dir_path.iterdir()):
                existing_dirs.append(dir_name)
        
        if existing_dirs and not replace_existing:
            print(f"\n⚠ Внимание! Найдены существующие данные в директориях: {', '.join(existing_dirs)}")
            print("Используйте --replace для замены существующих данных")
            return False
        
        # Создаем резервную копию перед восстановлением (если нужно)
        if existing_dirs and create_backup_before:
            print(f"\n⚠ Создание резервной копии текущих данных перед восстановлением...")
            try:
                pre_restore_backup = self.create_backup(
                    include_html=restore_html,
                    include_pdf=restore_pdf,
                    comment=f"Автоматическая резервная копия перед восстановлением из {backup_path.name}"
                )
                print(f"✓ Резервная копия создана: {pre_restore_backup}")
            except Exception as e:
                print(f"⚠ Предупреждение: не удалось создать резервную копию: {e}")
                response = input("Продолжить восстановление без резервной копии? (yes/no): ")
                if response.lower() not in ['yes', 'y', 'да', 'д']:
                    print("Восстановление отменено")
                    return False
        
        if existing_dirs:
            print(f"\n⚠ Внимание! Существующие данные будут заменены в директориях:")
            for dir_name in existing_dirs:
                dir_path = self.base_dir / dir_name
                print(f"  - {dir_name}/")
        
        # Проверяем существующие данные
        existing_dirs = []
        for dir_name in self.WORKING_DIRECTORIES:
            dir_path = self.base_dir / dir_name
            if dir_path.exists() and any(dir_path.iterdir()):
                existing_dirs.append(dir_name)
        
        if existing_dirs and not replace_existing:
            print(f"\n⚠ Внимание! Найдены существующие данные в директориях: {', '.join(existing_dirs)}")
            print("Используйте --replace для замены существующих данных")
            return False
        
        if existing_dirs:
            print(f"\n⚠ Внимание! Существующие данные будут заменены в директориях:")
            for dir_name in existing_dirs:
                dir_path = self.base_dir / dir_name
                print(f"  - {dir_name}/")
        
        # Подтверждение
        print(f"\nВосстановление из: {backup_path}")
        print(f"В директорию: {self.base_dir}")
        
        try:
            # Создаем временную директорию для распаковки
            temp_dir = self.base_dir / '.restore_temp'
            temp_dir.mkdir(exist_ok=True)
            
            try:
                # Распаковываем архив
                print("\nРаспаковка архива...")
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)
                
                # Восстанавливаем директории
                print("\nВосстановление директорий...")
                for dir_name in self.WORKING_DIRECTORIES:
                    source_dir = temp_dir / dir_name
                    
                    # Пропускаем HTML и PDF если не нужно восстанавливать
                    if dir_name == 'html' and not restore_html:
                        continue
                    if dir_name == 'pdf' and not restore_pdf:
                        continue
                    
                    if source_dir.exists():
                        target_dir = self.base_dir / dir_name
                        
                        # Удаляем существующую директорию если нужно
                        if target_dir.exists() and replace_existing:
                            print(f"  Удаление существующей директории: {dir_name}/")
                            shutil.rmtree(target_dir)
                        
                        # Копируем директорию
                        print(f"  Восстановление: {dir_name}/")
                        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
                
                # Восстанавливаем файлы
                print("\nВосстановление файлов...")
                for file_name in self.WORKING_FILES:
                    source_file = temp_dir / file_name
                    if source_file.exists():
                        target_file = self.base_dir / file_name
                        print(f"  Восстановление: {file_name}")
                        shutil.copy2(source_file, target_file)
                
                # Удаляем временную директорию
                shutil.rmtree(temp_dir)
                
                print(f"\n✓ Восстановление успешно завершено!")
                return True
                
            except Exception as e:
                # Очищаем временную директорию при ошибке
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise
                
        except Exception as e:
            print(f"\n✗ Ошибка при восстановлении: {e}")
            return False


def main():
    """CLI интерфейс для резервного копирования и восстановления"""
    parser = argparse.ArgumentParser(
        description='Резервное копирование и восстановление рабочих данных'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Команда')
    
    # Команда backup
    backup_parser = subparsers.add_parser('backup', help='Создать резервную копию')
    backup_parser.add_argument(
        '--backup-dir',
        type=str,
        default='backups',
        help='Директория для хранения резервных копий (по умолчанию: backups)'
    )
    backup_parser.add_argument(
        '--no-html',
        action='store_true',
        help='Не включать HTML файлы в резервную копию'
    )
    backup_parser.add_argument(
        '--no-pdf',
        action='store_true',
        help='Не включать PDF файлы в резервную копию'
    )
    backup_parser.add_argument(
        '--comment',
        type=str,
        help='Комментарий к резервной копии'
    )
    
    # Команда restore
    restore_parser = subparsers.add_parser('restore', help='Восстановить из резервной копии')
    restore_parser.add_argument(
        'backup_file',
        type=str,
        help='Путь к файлу резервной копии или номер из списка'
    )
    restore_parser.add_argument(
        '--backup-dir',
        type=str,
        default='backups',
        help='Директория с резервными копиями (по умолчанию: backups)'
    )
    restore_parser.add_argument(
        '--replace',
        action='store_true',
        help='Заменять существующие данные'
    )
    restore_parser.add_argument(
        '--no-html',
        action='store_true',
        help='Не восстанавливать HTML файлы'
    )
    restore_parser.add_argument(
        '--no-pdf',
        action='store_true',
        help='Не восстанавливать PDF файлы'
    )
    restore_parser.add_argument(
        '--no-backup-before',
        action='store_true',
        help='Не создавать резервную копию перед восстановлением'
    )
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Список резервных копий')
    list_parser.add_argument(
        '--backup-dir',
        type=str,
        default='backups',
        help='Директория с резервными копиями (по умолчанию: backups)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    backup_restore = BackupRestore(backup_dir=args.backup_dir)
    
    if args.command == 'backup':
        backup_path = backup_restore.create_backup(
            include_html=not args.no_html,
            include_pdf=not args.no_pdf,
            comment=args.comment
        )
        print(f"\nРезервная копия сохранена: {backup_path}")
    
    elif args.command == 'restore':
        # Определяем путь к резервной копии
        backup_file = args.backup_file
        
        # Если это число, берем из списка
        if backup_file.isdigit():
            backups = backup_restore.list_backups()
            try:
                index = int(backup_file) - 1
                if 0 <= index < len(backups):
                    backup_file = backups[index]['path']
                else:
                    print(f"✗ Неверный номер резервной копии. Доступно: {len(backups)}")
                    return
            except ValueError:
                pass
        
        # Если это не полный путь, ищем в директории резервных копий
        backup_path = Path(backup_file)
        if not backup_path.is_absolute():
            backup_path = backup_restore.backup_dir / backup_file
        
        success = backup_restore.restore_backup(
            backup_path,
            replace_existing=args.replace,
            restore_html=not args.no_html,
            restore_pdf=not args.no_pdf,
            create_backup_before=not args.no_backup_before
        )
        
        if not success:
            sys.exit(1)
    
    elif args.command == 'list':
        backups = backup_restore.list_backups()
        
        if not backups:
            print("Резервные копии не найдены")
            return
        
        print(f"\nНайдено резервных копий: {len(backups)}\n")
        print(f"{'№':<4} {'Дата создания':<20} {'Размер':<12} {'Комментарий':<30}")
        print("-" * 80)
        
        for i, backup in enumerate(backups, 1):
            timestamp = backup['timestamp']
            try:
                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Пробуем другие форматы
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = timestamp
            
            size_mb = backup['size'] / (1024 * 1024)
            comment = backup['metadata'].get('comment', '')[:30] if backup['metadata'] else ''
            
            print(f"{i:<4} {date_str:<20} {size_mb:>8.2f} MB  {comment:<30}")


if __name__ == "__main__":
    main()

