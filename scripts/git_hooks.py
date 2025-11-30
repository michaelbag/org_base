"""
Git hooks для автоматического отслеживания изменений документов
"""
import os
import sys
from pathlib import Path
import subprocess

# Добавляем путь к скриптам
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_tracker import VersionTracker


def get_git_author():
    """Получает автора из Git конфигурации"""
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "unknown"


def get_git_email():
    """Получает email из Git конфигурации"""
    try:
        result = subprocess.run(
            ['git', 'config', 'user.email'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "unknown@example.com"


def get_commit_message():
    """Получает сообщение коммита"""
    try:
        commit_file = os.environ.get('GIT_EDITOR') or '.git/COMMIT_EDITMSG'
        if os.path.exists(commit_file):
            with open(commit_file, 'r') as f:
                return f.read().strip()
    except:
        pass
    return ""


def pre_commit_hook():
    """Git pre-commit hook для отслеживания изменений"""
    base_dir = Path(__file__).parent.parent
    documents_dir = base_dir / "documents"
    tracker = VersionTracker(str(documents_dir))
    
    # Получаем измененные файлы
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            cwd=base_dir
        )
        
        if result.returncode == 0:
            changed_files = result.stdout.strip().split('\n')
            
            author = get_git_author()
            commit_msg = get_commit_message()
            
            for file_path in changed_files:
                if file_path.endswith('.md') and file_path.startswith('documents/'):
                    full_path = base_dir / file_path
                    if full_path.exists():
                        tracker.track_change(
                            full_path,
                            author,
                            f"Git commit: {commit_msg[:100]}"
                        )
    except Exception as e:
        print(f"Ошибка в pre-commit hook: {e}")
        # Не блокируем коммит при ошибке


if __name__ == "__main__":
    pre_commit_hook()

