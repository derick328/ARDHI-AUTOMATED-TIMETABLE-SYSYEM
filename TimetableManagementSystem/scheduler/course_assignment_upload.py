"""
Upload parser for Course-Lecturer Assignment Excel file.
Single-sheet .xlsx with two columns: Course_Code, Lecturer_Name
"""
import openpyxl
from .models import Course, Lecturer, UploadedCourseAssignment

COLUMN_ALIASES = {
    'course_code':   ['course_code', 'code', 'course code', 'subject_code'],
    'lecturer_name': ['lecturer_name', 'lecturer', 'name', 'staff', 'instructor'],
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


def parse_course_assignments(file_obj):
    """
    Parse course-lecturer assignment Excel and update Course.lecturer FK.

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

    required = ['course_code', 'lecturer_name']
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
            course_code_raw = row[col_map['course_code']]
            lecturer_name_raw = row[col_map['lecturer_name']]

            course_code = str(course_code_raw).strip() if course_code_raw else None
            lecturer_name = str(lecturer_name_raw).strip() if lecturer_name_raw else None

            if not course_code or course_code.lower() in ('none', 'null', ''):
                continue

            if not lecturer_name or lecturer_name.lower() in ('none', 'null', ''):
                errors.append(f"Row {row_idx}: Missing lecturer name for course '{course_code}'")
                UploadedCourseAssignment.objects.create(
                    course_code=course_code,
                    lecturer_name='',
                    status='error',
                    error_message='Missing lecturer name',
                )
                continue

            # Lookup course (case-insensitive)
            try:
                course = Course.objects.get(code__iexact=course_code)
            except Course.DoesNotExist:
                errors.append(f"Row {row_idx}: Course '{course_code}' not found in database")
                UploadedCourseAssignment.objects.create(
                    course_code=course_code,
                    lecturer_name=lecturer_name,
                    status='error',
                    error_message=f"Course '{course_code}' not found",
                )
                continue

            # Lookup lecturer (case-insensitive, partial name match)
            lecturers = Lecturer.objects.filter(name__icontains=lecturer_name)
            if not lecturers.exists():
                # Try exact match
                lecturers = Lecturer.objects.filter(name__iexact=lecturer_name)
            if not lecturers.exists():
                errors.append(f"Row {row_idx}: Lecturer '{lecturer_name}' not found in database")
                UploadedCourseAssignment.objects.create(
                    course_code=course_code,
                    lecturer_name=lecturer_name,
                    status='error',
                    error_message=f"Lecturer '{lecturer_name}' not found",
                )
                continue

            lecturer = lecturers.first()
            course.lecturer = lecturer
            course.save(update_fields=['lecturer'])

            UploadedCourseAssignment.objects.create(
                course_code=course_code,
                lecturer_name=lecturer.name,
                status='success',
            )
            success_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error — {e}")

    return {'success_count': success_count, 'errors': errors}
