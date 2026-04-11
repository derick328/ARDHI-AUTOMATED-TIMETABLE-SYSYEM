"""
Upload parser for Lecturer/Course-Assignment Excel file.
Single-sheet .xlsx with 2 columns:
  Course_Code, Lecturer_Name
Column names are flexible — uses alias matching.

For each row:
  - Looks up Course by code (case-insensitive).
  - Looks up Lecturer by name (case-insensitive). Creates one if not found,
    with an auto-generated email: first.last@ardhi.ac.tz
  - Links the course to the lecturer (course.lecturer = lecturer).
"""
import re
import openpyxl
from .models import Course, Lecturer

COLUMN_ALIASES = {
    'course_code':   ['course_code', 'code', 'course_code', 'course code', 'subject_code', 'module_code', 'coursecode'],
    'lecturer_name': ['lecture_name', 'lecturer_name', 'lecture name', 'lecturer name',
                      'Lecture Name', 'Lecturer Name', 'name', 'lecturer', 'staff_name', 'instructor', 'teacher'],
}


def _normalize(value):
    if not value and value != 0:
        return ''
    # Strip, lowercase, collapse all whitespace/underscores to a single underscore
    s = str(value).strip().lower()
    s = re.sub(r'[\s_]+', '_', s)   # handles non-breaking spaces, tabs, etc.
    s = re.sub(r'[^\w]', '', s)     # drop any remaining non-word chars
    return s


def _detect_columns(headers):
    col_map = {}
    normalized = [_normalize(h) for h in headers]
    for canonical, aliases in COLUMN_ALIASES.items():
        norm_aliases = {_normalize(a) for a in aliases}
        for idx, h in enumerate(normalized):
            if h in norm_aliases:
                col_map[canonical] = idx
                break
    return col_map


def _auto_email(name):
    """Generate a placeholder email from a lecturer name."""
    slug = re.sub(r'[^a-z0-9]+', '.', name.lower().strip()).strip('.')
    return f"{slug}@ardhi.ac.tz"


def parse_lecturers(file_obj):
    """
    Parse a course-lecturer assignment Excel file and:
      - Auto-create Lecturer records by name (if not already present).
      - Link each Course to its Lecturer.

    Returns:
        {'success_count': int, 'linked_count': int, 'errors': [str]}
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {'success_count': 0, 'linked_count': 0, 'errors': [f"Cannot open file: {e}"]}

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {'success_count': 0, 'linked_count': 0, 'errors': ['File is empty']}

    headers = rows[0]
    col_map = _detect_columns(headers)

    required = ['course_code', 'lecturer_name']
    missing = [r for r in required if r not in col_map]
    if missing:
        return {
            'success_count': 0,
            'linked_count': 0,
            'errors': [f"Missing required columns: {missing}. Found: {list(headers)}"]
        }

    success_count = 0
    linked_count = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            raw_code = row[col_map['course_code']]
            raw_name = row[col_map['lecturer_name']]

            course_code = str(raw_code).strip() if raw_code else None
            lecturer_name = str(raw_name).strip() if raw_name else None

            if not course_code or course_code.lower() in ('none', 'null', ''):
                errors.append(f"Row {row_idx}: missing course code — skipped")
                continue
            if not lecturer_name or lecturer_name.lower() in ('none', 'null', ''):
                errors.append(f"Row {row_idx}: missing lecturer name — skipped")
                continue

            # Look up or create lecturer by name (always — even if course not found yet)
            lecturer = Lecturer.objects.filter(name__iexact=lecturer_name).first()
            if not lecturer:
                email = _auto_email(lecturer_name)
                # Ensure email uniqueness
                if Lecturer.objects.filter(email=email).exists():
                    base = email.rsplit('@', 1)[0]
                    email = f"{base}.{row_idx}@ardhi.ac.tz"
                lecturer = Lecturer.objects.create(
                    name=lecturer_name,
                    email=email,
                    is_full_time=True,
                )
                success_count += 1

            # Look up course and link (optional — skip if course not uploaded yet)
            try:
                course = Course.objects.get(code__iexact=course_code)
                course.lecturer = lecturer
                course.save(update_fields=['lecturer'])
                linked_count += 1
            except Course.DoesNotExist:
                errors.append(
                    f"Row {row_idx}: lecturer '{lecturer_name}' saved, "
                    f"but course '{course_code}' not found — upload curriculum first to link"
                )
            except Course.MultipleObjectsReturned:
                errors.append(
                    f"Row {row_idx}: lecturer '{lecturer_name}' saved, "
                    f"but multiple courses match '{course_code}' — link manually"
                )

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error — {e}")

    return {
        'success_count': success_count,
        'linked_count': linked_count,
        'errors': errors,
    }
