"""
Парсер карточек сотрудников из Markdown с YAML front matter
"""
import os
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class EmployeeParser:
    """Парсер карточек сотрудников в формате Markdown с метаданными"""
    
    def __init__(self, documents_dir: str = "documents"):
        self.documents_dir = Path(documents_dir)
    
    def parse_employee(self, file_path: Path) -> Optional[Dict]:
        """Парсит карточку сотрудника и возвращает метаданные"""
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
            
            # Извлекаем организацию и отдел из пути
            parts = file_path.relative_to(self.documents_dir).parts
            if len(parts) >= 2:
                metadata['organization'] = metadata.get('organization', parts[0])
                # Ищем отдел (может быть в разных местах пути)
                for i, part in enumerate(parts):
                    if part in ['сотрудники', 'employees'] and i > 0:
                        metadata['department'] = metadata.get('department', parts[i-1])
                        break
                if 'department' not in metadata and len(parts) >= 2:
                    metadata['department'] = metadata.get('department', parts[1])
            
            # Определяем доступность
            if 'dismissal_date' in metadata and metadata['dismissal_date']:
                metadata['available'] = False
            else:
                metadata['available'] = metadata.get('available', True)
            
            # Добавляем содержимое, если есть
            if markdown_content.strip():
                metadata['content'] = markdown_content.strip()
            
            return metadata
        except Exception as e:
            print(f"Ошибка при парсинге карточки сотрудника {file_path}: {e}")
            return None
    
    def get_employee_by_name(self, full_name: str, organization: Optional[str] = None, department: Optional[str] = None) -> Optional[Dict]:
        """Находит сотрудника по ФИО"""
        # Сначала ищем в указанном отделе
        if department:
            employees = self.get_all_employees(organization=organization, department=department)
            for emp in employees:
                if emp.get('full_name', '').strip() == full_name.strip():
                    return emp
        
        # Если не найдено в указанном отделе, ищем по всей организации
        employees = self.get_all_employees(organization=organization, department=None)
        for emp in employees:
            if emp.get('full_name', '').strip() == full_name.strip():
                return emp
        return None
    
    def get_all_employees(self, organization: Optional[str] = None, department: Optional[str] = None) -> List[Dict]:
        """Получает список всех сотрудников с опциональной фильтрацией"""
        employees = []
        employees_dir = self.documents_dir
        
        # Ищем папки "сотрудники" или "employees" в структуре
        for org_dir in employees_dir.iterdir():
            if not org_dir.is_dir():
                continue
            
            # Ищем в отделах
            for dept_dir in org_dir.iterdir():
                if not dept_dir.is_dir():
                    continue
                
                if department and dept_dir.name != department:
                    continue
                
                # Ищем папку сотрудников
                employees_folder = dept_dir / "сотрудники"
                if not employees_folder.exists():
                    employees_folder = dept_dir / "employees"
                
                if employees_folder.exists() and employees_folder.is_dir():
                    for emp_file in employees_folder.glob("*.md"):
                        employee = self.parse_employee(emp_file)
                        if employee:
                            # Фильтруем по организации из метаданных файла
                            if organization:
                                emp_org = employee.get('organization', '')
                                # Нормализуем сравнение (убираем кавычки и пробелы)
                                org_normalized = organization.replace('"', '').strip()
                                emp_org_normalized = emp_org.replace('"', '').strip()
                                if org_normalized != emp_org_normalized:
                                    continue
                            employees.append(employee)
        
        return employees
    
    def get_employees_by_department(self, organization: str, department: str) -> List[Dict]:
        """Получает список сотрудников отдела"""
        return self.get_all_employees(organization=organization, department=department)
    
    def get_available_employees(self, organization: Optional[str] = None, department: Optional[str] = None) -> List[Dict]:
        """Получает список доступных (не уволенных) сотрудников"""
        all_employees = self.get_all_employees(organization=organization, department=department)
        return [emp for emp in all_employees if emp.get('available', True)]

