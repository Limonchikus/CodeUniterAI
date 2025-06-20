import os
import ast
import json
from pathlib import Path
from datetime import datetime
import re


class ProjectCollector:
    def __init__(self, root_dir='.', exclude_dirs=None, exclude_files=None):
        self.root_dir = Path(root_dir)
        self.exclude_dirs = exclude_dirs or {'__pycache__', '.git', '.venv', 'venv', 'node_modules', '.idea'}
        self.exclude_files = exclude_files or {'*.pyc', '*.pyo', '.DS_Store'}

    def analyze_python_file(self, filepath):
        """Анализ Python файла: функции, классы, импорты"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            analysis = {
                'imports': [],
                'functions': [],
                'classes': [],
                'docstring': ast.get_docstring(tree),
                'lines': len(content.splitlines())
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    analysis['imports'].extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis['imports'].append(f"{node.module}.{', '.join([alias.name for alias in node.names])}")
                elif isinstance(node, ast.FunctionDef):
                    analysis['functions'].append({
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node),
                        'line': node.lineno
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis['classes'].append({
                        'name': node.name,
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        'docstring': ast.get_docstring(node),
                        'line': node.lineno
                    })

            return analysis
        except Exception as e:
            return {'error': str(e)}

    def collect_files(self, extensions=None):
        """Сбор файлов по расширениям"""
        extensions = extensions or ['.py', '.md', '.txt', '.yml', '.yaml', '.json']
        files_info = []

        for root, dirs, files in os.walk(self.root_dir):
            # Исключаем ненужные директории
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                filepath = Path(root) / file
                if filepath.suffix in extensions:
                    rel_path = filepath.relative_to(self.root_dir)

                    info = {
                        'path': str(rel_path),
                        'size': filepath.stat().st_size,
                        'extension': filepath.suffix
                    }

                    # Специальный анализ для Python файлов
                    if filepath.suffix == '.py':
                        info['analysis'] = self.analyze_python_file(filepath)

                    files_info.append(info)

        return files_info

    def generate_tree_structure(self):
        """Генерация древовидной структуры"""
        tree = {}
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            rel_root = os.path.relpath(root, self.root_dir)
            if rel_root == '.':
                current_level = tree
            else:
                path_parts = rel_root.split(os.sep)
                current_level = tree
                for part in path_parts:
                    if part not in current_level:
                        current_level[part] = {}
                    current_level = current_level[part]

            for file in files:
                if not any(file.endswith(ext.replace('*', '')) for ext in self.exclude_files):
                    current_level[file] = 'file'

        return tree

    def print_tree(self, tree, prefix="", is_last=True):
        """Красивый вывод дерева"""
        items = list(tree.items())
        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1

            if subtree == 'file':
                print(f"{prefix}{'└── ' if is_last_item else '├── '}{name}")
            else:
                print(f"{prefix}{'└── ' if is_last_item else '├── '}{name}/")
                extension = "    " if is_last_item else "│   "
                self.print_tree(subtree, prefix + extension, is_last_item)

    def generate_summary_report(self, output_file='project_summary.md'):
        """Генерация подробного отчета"""
        files_info = self.collect_files()
        tree = self.generate_tree_structure()

        # Статистика
        total_files = len(files_info)
        python_files = [f for f in files_info if f['extension'] == '.py']
        total_lines = sum(f.get('analysis', {}).get('lines', 0) for f in python_files)

        # Сбор всех функций и классов
        all_functions = []
        all_classes = []
        all_imports = set()

        for file_info in python_files:
            analysis = file_info.get('analysis', {})
            if 'functions' in analysis:
                for func in analysis['functions']:
                    func['file'] = file_info['path']
                    all_functions.append(func)
            if 'classes' in analysis:
                for cls in analysis['classes']:
                    cls['file'] = file_info['path']
                    all_classes.append(cls)
            if 'imports' in analysis:
                all_imports.update(analysis['imports'])

        # Генерация отчета
        report = f"""# Отчет по проекту
Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Общая статистика
- Всего файлов: {total_files}
- Python файлов: {len(python_files)}
- Строк кода: {total_lines}
- Функций: {len(all_functions)}
- Классов: {len(all_classes)}
- Уникальных импортов: {len(all_imports)}

## Структура проекта
```
{self.root_dir.name}/
"""

        # Добавляем дерево структуры (в виде строки)
        import io
        from contextlib import redirect_stdout

        tree_output = io.StringIO()
        with redirect_stdout(tree_output):
            self.print_tree(tree)

        report += tree_output.getvalue()
        report += "```\n\n"

        # Основные компоненты
        if all_classes:
            report += "## Основные классы\n"
            for cls in sorted(all_classes, key=lambda x: x['name']):
                report += f"- **{cls['name']}** ({cls['file']})\n"
                if cls['docstring']:
                    report += f"  - {cls['docstring'][:100]}...\n"
                if cls['methods']:
                    report += f"  - Методы: {', '.join(cls['methods'])}\n"
            report += "\n"

        if all_functions:
            report += "## Основные функции\n"
            for func in sorted(all_functions, key=lambda x: x['name'])[:20]:  # Топ 20
                report += f"- **{func['name']}()** ({func['file']})\n"
                if func['docstring']:
                    report += f"  - {func['docstring'][:100]}...\n"
                if func['args']:
                    report += f"  - Аргументы: {', '.join(func['args'])}\n"
            report += "\n"

        # Зависимости
        if all_imports:
            report += "## Основные зависимости\n"
            for imp in sorted(all_imports)[:15]:  # Топ 15
                report += f"- {imp}\n"
            report += "\n"

        # Сохранение отчета
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        return report

    def create_consolidated_code(self, output_file='consolidated_code.py', max_file_size=50000):
        """Создание объединенного файла с кодом"""
        python_files = [f for f in self.collect_files() if f['extension'] == '.py']

        consolidated = f'''"""
=== ОБЪЕДИНЕННЫЙ КОД ПРОЕКТА ===
Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Файлов: {len(python_files)}

СТРУКТУРА:
"""

'''

        for file_info in python_files:
            filepath = self.root_dir / file_info['path']

            # Пропускаем слишком большие файлы
            if file_info['size'] > max_file_size:
                consolidated += f"# === {file_info['path']} === [ФАЙЛ СЛИШКОМ БОЛЬШОЙ: {file_info['size']} байт]\n\n"
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                consolidated += f"# {'=' * 50}\n"
                consolidated += f"# ФАЙЛ: {file_info['path']}\n"
                consolidated += f"# РАЗМЕР: {file_info['size']} байт\n"

                # Добавляем анализ если есть
                analysis = file_info.get('analysis', {})
                if analysis.get('functions'):
                    consolidated += f"# ФУНКЦИИ: {', '.join([f['name'] for f in analysis['functions']])}\n"
                if analysis.get('classes'):
                    consolidated += f"# КЛАССЫ: {', '.join([c['name'] for c in analysis['classes']])}\n"

                consolidated += f"# {'=' * 50}\n\n"
                consolidated += content + "\n\n"

            except Exception as e:
                consolidated += f"# === {file_info['path']} === [ОШИБКА ЧТЕНИЯ: {e}]\n\n"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(consolidated)

        return consolidated


# Использование
if __name__ == "__main__":
    collector = ProjectCollector('.')

    # Генерация отчета
    print("Генерация отчета...")
    report = collector.generate_summary_report()
    print("Отчет сохранен в project_summary.md")

    # Создание объединенного кода
    print("Создание объединенного кода...")
    consolidated = collector.create_consolidated_code()
    print("Код сохранен в consolidated_code.py")

    # Вывод структуры в консоль
    print("\nСтруктура проекта:")
    tree = collector.generate_tree_structure()
    collector.print_tree(tree)
