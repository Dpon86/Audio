"""Fix misplaced force_authenticate imports and re-check all test files."""
import os
import re

test_dir = r'C:\Users\NickD\Documents\Github\Audio\backend\audioDiagnostic\tests'
IMPORT_LINE = 'from rest_framework.test import force_authenticate'


def fix_misplaced_import(fname):
    """Remove any indented force_authenticate imports and ensure one top-level one exists."""
    path = os.path.join(test_dir, fname)
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1') as f:
            content = f.read()

    # Check if there's a misplaced (indented) import
    has_indented = bool(re.search(r'^[ \t]+from rest_framework\.test import force_authenticate', content, re.MULTILINE))
    has_toplevel = bool(re.search(r'^from rest_framework\.test import force_authenticate', content, re.MULTILINE))

    # Check if top-level import is in the correct position (before first class/def/test code)
    import_pos = -1
    first_classdef_pos = -1
    for i, line in enumerate(content.split('\n')):
        if 'from rest_framework.test import force_authenticate' in line and not line.startswith(' ') and not line.startswith('\t'):
            import_pos = i
        if (line.startswith('class ') or line.startswith('def ')) and first_classdef_pos == -1:
            first_classdef_pos = i

    toplevel_in_right_place = (import_pos != -1 and first_classdef_pos != -1 and import_pos < first_classdef_pos)

    if not has_indented and has_toplevel and toplevel_in_right_place:
        return False  # Already correct

    # Remove all existing force_authenticate imports (both indented and top-level)
    lines = content.split('\n')
    cleaned = [l for l in lines if 'from rest_framework.test import force_authenticate' not in l]

    # Find correct insertion point: after the last top-level 'from rest_framework' or 'from django' or 'import ' line
    insert_at = 0
    for i, line in enumerate(cleaned):
        stripped = line.lstrip()
        # Only look at top-level imports (no indentation)
        if not line.startswith(' ') and not line.startswith('\t'):
            if (stripped.startswith('from rest_framework') or
                    stripped.startswith('from django') or
                    stripped.startswith('import ') or
                    stripped.startswith('from ')):
                insert_at = i + 1

    cleaned.insert(insert_at, IMPORT_LINE)
    new_content = '\n'.join(cleaned)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    except Exception:
        with open(path, 'w', encoding='latin-1') as f:
            f.write(new_content)

    print(f'  Fixed import in {fname} (insert_at={insert_at})')
    return True


# Fix all test files
all_files = [f for f in os.listdir(test_dir) if f.endswith('.py')]
fixed = 0
for fname in sorted(all_files):
    if fix_misplaced_import(fname):
        fixed += 1

print(f'Total files fixed: {fixed}')


