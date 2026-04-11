"""
Upload parser for Lecturers Excel file.
Single-sheet .xlsx with columns:
  Name, Email, Is_Full_Time
Column names are flexible — uses alias matching.
"""
import openpyxl
from .models import Lecturer

COLUMN_ALIASES = {
    'name':         ['name', 'lecturer_name', 'full_name', 'lecturer', 'staff_name'],
    'email':        ['email', 'email_address', 'mail', 'e_mail'],
    'is_full_time': ['is_full_time', 'full_time', 'fulltime', 'employment_type', 'type'],
}


def _normalize(value):
    return str(value).strip().lower().replace(' ', '_') if value else ''


def _detect_columns(headers):
    col_map = {}
    normalized = [_normalize(h) for h in headers]
    for canonical, aliases in COLUMN_ALIASES.items():
        for idx, h in enumerate(normalized):
            if h in aliases:
                col_map[canonical] = idx
                break
    return col_map


def _parse_bool(value):
    if value is None:
        return True  # default: full-time
    return str(value).strip().lower() in ('yes', 'true', '1', 'y', 'full_time', 'full-time')


def parse_lecturers(file_obj):
    """
    Parse a lecturers Excel file and create/update Lecturer records.

    Returns:
        {'success_count': int, 'errors': [str]}
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {'success_count': 0, 'errors': [f"Cannot open file: {e}"]}

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {'success_count': 0, 'errors': ['File is empty']}

    headers = rows[0]
    col_map = _detect_columns(headers)

    required = ['name', 'email']
    missing = [r for r in required if r not in col_map]
    if missing:
        return {
            'success_count': 0,
            'errors': [f"Missing required columns: {missing}. Found: {list(headers)}"]
        }

    success_count = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            name = str(row[col_map['name']]).strip() if row[col_map['name']] else None
            email_raw = row[col_map['email']]
            email = str(email_raw).strip().lower() if email_raw else None
            is_full_time_raw = row[col_map.get('is_full_time', -1)] if 'is_full_time' in col_map else True

            if not name or name.lower() in ('none', 'null', ''):
                errors.append(f"Row {row_idx}: Missing lecturer name — skipped")
                continue

            if not email or '@' not in email or email.lower() in ('none', 'null'):
                errors.append(f"Row {row_idx}: Invalid email '{email}' for lecturer '{name}'")
                continue

            is_full_time = _parse_bool(is_full_time_raw)

            Lecturer.objects.update_or_create(
                email=email,
                defaults={'name': name, 'is_full_time': is_full_time}
            )
            success_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error — {e}")

    return {'success_count': success_count, 'errors': errors}
