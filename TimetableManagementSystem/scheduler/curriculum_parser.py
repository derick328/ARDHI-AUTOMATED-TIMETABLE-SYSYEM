"""
Upload parser for Curriculum Excel file.
Multi-sheet .xlsx — one sheet per programme (sheet name = programme name or code).
Columns per sheet: Course_Code, Course_Title, Semester, Study_Year, Is_Exam, Is_Lab
"""
import openpyxl
from .models import Programme, Course

COLUMN_ALIASES = {
    'course_code':  ['course_code', 'code', 'course code', 'subject_code', 'module_code'],
    'course_title': ['course_title', 'title', 'course title', 'course_name', 'subject', 'module'],
    'semester':     ['semester', 'sem', 'semester_number'],
    'study_year':   ['study_year', 'year', 'year_of_study', 'level', 'stage'],
    'is_exam':      ['is_exam', 'exam', 'examination', 'is_examination'],
    'is_lab':       ['is_lab', 'lab', 'laboratory', 'practical'],
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
        return False
    return str(value).strip().lower() in ('yes', 'true', '1', 'y')


def _parse_int(value, field_name, row_idx):
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        raise ValueError(f"Row {row_idx}: Invalid integer for '{field_name}': '{value}'")


def parse_curriculum(file_obj):
    """
    Parse multi-sheet curriculum Excel and create/update Course records.
    Each sheet name must match an existing Programme name or code (case-insensitive).

    Returns:
        {'success_count': int, 'errors': [str], 'sheets_processed': [str]}
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {'success_count': 0, 'errors': [f"Cannot open file: {e}"], 'sheets_processed': []}

    # Build a lookup: normalized name/code -> Programme object
    all_programmes = list(Programme.objects.select_related('school').all())
    prog_lookup = {}
    for p in all_programmes:
        prog_lookup[p.name.lower()] = p
        prog_lookup[p.code.lower()] = p

    total_success = 0
    all_errors = []
    sheets_processed = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            all_errors.append(f"Sheet '{sheet_name}': empty — skipped")
            continue

        # Match sheet name to a Programme
        programme = prog_lookup.get(sheet_name.strip().lower())
        if not programme:
            all_errors.append(
                f"Sheet '{sheet_name}': no Programme found matching this name or code — skipped"
            )
            continue

        headers = rows[0]
        col_map = _detect_columns(headers)

        required = ['course_code', 'course_title', 'semester', 'study_year']
        missing = [r for r in required if r not in col_map]
        if missing:
            all_errors.append(
                f"Sheet '{sheet_name}': missing columns {missing}. Found: {list(headers)}"
            )
            continue

        sheet_success = 0
        for row_idx, row in enumerate(rows[1:], start=2):
            try:
                course_code = str(row[col_map['course_code']]).strip() if row[col_map['course_code']] else None
                course_title = str(row[col_map['course_title']]).strip() if row[col_map['course_title']] else None

                if not course_code or course_code.lower() in ('none', 'null', ''):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: missing course code — skipped")
                    continue
                if not course_title or course_title.lower() in ('none', 'null', ''):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: missing course title — skipped")
                    continue

                semester = _parse_int(row[col_map['semester']], 'semester', row_idx)
                study_year = _parse_int(row[col_map['study_year']], 'study_year', row_idx)

                if semester not in (1, 2):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: semester must be 1 or 2, got '{semester}'")
                    continue
                if study_year not in (1, 2, 3, 4):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: study_year must be 1-4, got '{study_year}'")
                    continue

                is_exam_raw = row[col_map.get('is_exam', -1)] if 'is_exam' in col_map else False
                is_lab_raw = row[col_map.get('is_lab', -1)] if 'is_lab' in col_map else False
                is_exam = _parse_bool(is_exam_raw)
                is_lab = _parse_bool(is_lab_raw)

                Course.objects.update_or_create(
                    code=course_code,
                    defaults={
                        'title': course_title,
                        'programme': programme,
                        'semester': semester,
                        'study_year': study_year,
                        'is_exam': is_exam,
                        'is_lab': is_lab,
                    }
                )
                sheet_success += 1

            except ValueError as ve:
                all_errors.append(f"Sheet '{sheet_name}' {ve}")
            except Exception as e:
                all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: {e}")

        total_success += sheet_success
        sheets_processed.append(f"{sheet_name} ({sheet_success} courses)")

    return {
        'success_count': total_success,
        'errors': all_errors,
        'sheets_processed': sheets_processed,
    }
