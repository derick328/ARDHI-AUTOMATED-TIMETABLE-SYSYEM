"""
Upload parser for Curriculum Excel file.
Multi-sheet .xlsx — one sheet per programme (sheet name = programme name or code).

Columns per sheet: S/N, Course_Code, Course_Name, Study_Period
  - S/N          : serial number — ignored
  - Course_Code  : unique course code
  - Course_Name  : course title/name
  - Study_Period : combined year+semester string, e.g. "Year 1:Semester 1"
                   Parsed to extract study_year and semester integers.

is_exam and is_lab default to False (update via other means if needed).
"""
import re
import openpyxl
from .models import Programme, Course

COLUMN_ALIASES = {
    'sn':           ['s/n', 'sn', 'no', 'number', '#', 's_n', 'serial'],
    'course_code':  ['course_code', 'code', 'course code', 'subject_code', 'module_code', 'coursecode'],
    'course_name':  ['course_name', 'name', 'course_title', 'course title', 'title', 'subject', 'module', 'course name'],
    'study_period': ['study_period', 'period', 'study period', 'year_semester', 'term', 'studyperiod'],
}


def _normalize(value):
    if not value and value != 0:
        return ''
    s = str(value).strip().lower()
    s = re.sub(r'[\s_]+', '_', s)   # collapse all whitespace variants to underscore
    s = re.sub(r'[^\w]', '', s)     # drop remaining non-word characters
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


def _parse_study_period(value):
    """
    Parse a study period string into (study_year, semester).
    Accepts formats like:
      "Year 1:Semester 1", "Year 1: Semester 1", "year1 sem2",
      "Y1S1", "1:1", "Year 2 Semester 1"
    Returns (study_year: int, semester: int).
    Raises ValueError if parsing fails.
    """
    s = str(value).lower().strip()

    # Try explicit "year X ... sem Y" pattern first
    year_match = re.search(r'year\s*(\d)', s)
    sem_match = re.search(r'sem(?:ester)?\s*(\d)', s)

    if year_match and sem_match:
        return int(year_match.group(1)), int(sem_match.group(1))

    # Try "Y1S1" shorthand
    short_match = re.match(r'y(\d)s(\d)', s.replace(' ', ''))
    if short_match:
        return int(short_match.group(1)), int(short_match.group(2))

    # Try plain "X:Y" or "X/Y"
    num_match = re.match(r'(\d)\s*[:\/]\s*(\d)', s)
    if num_match:
        return int(num_match.group(1)), int(num_match.group(2))

    raise ValueError(f"Cannot parse study period: '{value}'")


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

        required = ['course_code', 'course_name', 'study_period']
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
                course_name = str(row[col_map['course_name']]).strip() if row[col_map['course_name']] else None
                study_period_raw = row[col_map['study_period']]

                if not course_code or course_code.lower() in ('none', 'null', ''):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: missing course code — skipped")
                    continue
                if not course_name or course_name.lower() in ('none', 'null', ''):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: missing course name — skipped")
                    continue
                if study_period_raw is None or str(study_period_raw).strip() == '':
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: missing study period — skipped")
                    continue

                try:
                    study_year, semester = _parse_study_period(study_period_raw)
                except ValueError as ve:
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: {ve}")
                    continue

                if semester not in (1, 2):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: semester must be 1 or 2, got '{semester}'")
                    continue
                if study_year not in (1, 2, 3, 4):
                    all_errors.append(f"Sheet '{sheet_name}' Row {row_idx}: study_year must be 1-4, got '{study_year}'")
                    continue

                Course.objects.update_or_create(
                    code=course_code,
                    defaults={
                        'title': course_name,
                        'programme': programme,
                        'semester': semester,
                        'study_year': study_year,
                        'is_exam': False,
                        'is_lab': False,
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
