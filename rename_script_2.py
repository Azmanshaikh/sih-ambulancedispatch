import os
import re

directories_to_scan = ['.']
exclude_dirs = ['.git', 'node_modules', '__pycache__', '.venv', 'venv']

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return

    original_content = content

    content = content.replace('Jeevan', 'Jeevan')
    content = content.replace('jeevan', 'jeevan')
    content = content.replace('jeevan', 'jeevan')
    content = content.replace('JEEVAN', 'JEEVAN')

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if file.endswith(('.py', '.js', '.jsx', '.html', '.css', '.md', '.json', '.txt', '.env.example', '.sql', '.yml')):
            replace_in_file(os.path.join(root, file))

print("Done replacing.")
