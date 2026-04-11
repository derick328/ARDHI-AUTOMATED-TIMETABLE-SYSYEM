"""
Upload parser for Rooms Excel file.
Single-sheet .xlsx with columns:
  Programme_Code, Room_Name, Capacity, Is_Lab
Column names are flexible — uses alias matching.
"""
import openpyxl
from .models import Room

COLUMN_ALIASES = {
    'room_name': ['room_name', 'room name', 'name', 'room', 'venue', 'venue_name'],
    'capacity':  ['capacity', 'cap', 'size', 'seats', 'max_capacity'],
    'is_lab':    ['is_lab', 'lab', 'laboratory', 'is_laboratory', 'lab_room'],
}


def _normalize(value):
    return str(value).strip().lower().replace(' ', '_') if value else ''


def _detect_columns(headers):
    """Map our canonical names to actual column indices (0-based)."""
    col_map = {}
    normalized_headers = [_normalize(h) for h in headers]
    for canonical, aliases in COLUMN_ALIASES.items():
        for idx, h in enumerate(normalized_headers):
            if h in aliases:
                col_map[canonical] = idx
                break
    return col_map


def _parse_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in ('yes', 'true', '1', 'y')


def parse_rooms(file_obj):
    """
    Parse a rooms Excel file and create/update Room records.

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

    required = ['room_name', 'capacity']
    missing = [r for r in required if r not in col_map]
    if missing:
        return {
            'success_count': 0,
            'errors': [f"Missing required columns: {missing}. Found headers: {list(headers)}"]
        }

    success_count = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            room_name = str(row[col_map['room_name']]).strip() if row[col_map['room_name']] else None
            capacity_raw = row[col_map['capacity']]
            is_lab_raw = row[col_map.get('is_lab', -1)] if 'is_lab' in col_map else False

            if not room_name or room_name.lower() in ('none', 'null', ''):
                errors.append(f"Row {row_idx}: Missing room name — skipped")
                continue

            try:
                capacity = int(float(str(capacity_raw)))
            except (ValueError, TypeError):
                errors.append(f"Row {row_idx}: Invalid capacity '{capacity_raw}' for room '{room_name}'")
                continue

            is_lab = _parse_bool(is_lab_raw)

            room, created = Room.objects.update_or_create(
                name=room_name,
                defaults={'capacity': capacity, 'is_lab': is_lab}
            )
            success_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error — {e}")

    return {'success_count': success_count, 'errors': errors}
