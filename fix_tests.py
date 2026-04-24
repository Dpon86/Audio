"""Fix pre-existing test errors in coverage boost test files."""
import os
import re

test_dir = r'C:\Users\NickD\Documents\Github\Audio\backend\audioDiagnostic\tests'

IMPORT_LINE = 'from rest_framework.test import force_authenticate'


def fix_req_user_assignments(test_dir):
    """Fix all X.user = self.Y patterns to use force_authenticate."""
    all_files = [f for f in os.listdir(test_dir) if f.endswith('.py')]
    total_fixed = 0

    for fname in all_files:
        path = os.path.join(test_dir, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()

        # Match: indentation + varname.user = self.something
        # Handles: request, req, drf_req etc.
        # Must be followed by word boundary (not request.user_id etc.)
        new_content = re.sub(
            r'(\s+)(\w+)\.user\s*=\s*(self\.\w+)\b',
            lambda m: m.group(1) + f'force_authenticate({m.group(2)}, user={m.group(3)})',
            content
        )

        # Add import if we added force_authenticate calls and it's not already there
        if 'force_authenticate' in new_content and IMPORT_LINE not in new_content:
            lines = new_content.split('\n')
            insert_at = 0
            for i, line in enumerate(lines):
                if 'from rest_framework' in line or 'import rest_framework' in line:
                    insert_at = i + 1
            lines.insert(insert_at, IMPORT_LINE)
            new_content = '\n'.join(lines)

        if new_content != content:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except Exception:
                with open(path, 'w', encoding='latin-1') as f:
                    f.write(new_content)
            count = len(re.findall(r'force_authenticate\(\w+, user=', new_content))
            print(f'  Fixed {fname}: {count} force_authenticate calls')
            total_fixed += 1

    return total_fixed


print('=== Comprehensive req.user fix ===')
n = fix_req_user_assignments(test_dir)
print(f'Total files fixed: {n}')

