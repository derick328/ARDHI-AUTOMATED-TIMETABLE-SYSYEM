"""
Upload parser for Lecturer/Course-Assignment Excel file.
Single-sheet .xlsx with 2 columns:
  Course_Code, Lecturer_Name
Column names are flexible — uses alias matching.

For each row:
  - Looks up Course by code (case-insensitive, any programme).
  - Looks up Lecturer by name (case-insensitive). Creates one if not found,
    with an auto-generated email: first.last@ardhi.ac.tz
  - Links the course(s) to the lecturer (course.lecturer = lecturer).

When the same course code appears N times with N different lecturers (shared
course taken by many programmes), the matching Course records are bin-packed
into N groups by student count (LPT heuristic) and assigned AUTO__CODE_G1…GN
merge_group labels so the scheduler places each group in an optimal venue.
"""
import re
from collections import OrderedDict
import openpyxl
from .models import Course, Lecturer, StudentCount

COLUMN_ALIASES = {
    'course_code':   ['course_code', 'code', 'course_code', 'course code', 'subject_code', 'module_code', 'coursecode'],
    'lecturer_name': ['lecture_name', 'lecturer_name', 'lecture name', 'lecturer name',
                      'Lecture Name', 'Lecturer Name', 'name', 'lecturer', 'staff_name', 'instructor', 'teacher'],
}

AUTO_MERGE_PREFIX = "AUTO__"


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


def _code_to_slug(code: str) -> str:
    """Produce a safe slug from a course code for use in merge_group labels."""
    slug = re.sub(r'[\s\-]+', '_', code.strip().upper())
    return re.sub(r'[^\w]', '', slug)


def _greedy_bin_pack(items_with_weights, n_bins):
    """
    Greedy LPT bin-packing: distribute items into n_bins minimising max bin weight.
    items_with_weights: list of (item, weight) sorted largest-first.
    Returns list of n_bins lists (each a list of items).
    """
    bins = [[] for _ in range(n_bins)]
    totals = [0] * n_bins
    for item, weight in items_with_weights:
        i = totals.index(min(totals))
        bins[i].append(item)
        totals[i] += weight
    return bins


def _find_courses(code):
    """Find all Course records matching a code (any programme). Tries multiple normalisations."""
    qs = Course.objects.filter(code__iexact=code).select_related('programme')
    if not qs.exists():
        qs = Course.objects.filter(code__iexact=code.replace(' ', '')).select_related('programme')
    if not qs.exists():
        qs = Course.objects.filter(code__iexact=re.sub(r'\s+', '', code)).select_related('programme')
    return list(qs)


def _student_count_for(course):
    sc = StudentCount.objects.filter(
        programme=course.programme, study_year=course.study_year
    ).first()
    return sc.total_count if sc else 0


def parse_lecturers(file_obj):
    """
    Parse a course-lecturer assignment Excel file and:
      - Auto-create Lecturer records by name (if not already present).
      - Link each Course to its Lecturer.
      - When a code appears N>1 times (multi-lecturer shared course), bin-pack
        degree programmes by student count into N balanced groups and assign
        AUTO__CODE_G{i} merge_group labels.

    Returns:
        {
          'success_count': int,      # new Lecturer records created
          'linked_count':  int,      # Course records updated
          'errors':        [str],
          'groups_created': [dict],  # non-empty when multi-lecturer groups were formed
        }
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {'success_count': 0, 'linked_count': 0, 'errors': [f"Cannot open file: {e}"], 'groups_created': []}

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {'success_count': 0, 'linked_count': 0, 'errors': ['File is empty'], 'groups_created': []}

    headers = rows[0]
    col_map = _detect_columns(headers)

    required = ['course_code', 'lecturer_name']
    missing = [r for r in required if r not in col_map]
    if missing:
        return {
            'success_count': 0,
            'linked_count': 0,
            'errors': [f"Missing required columns: {missing}. Found: {list(headers)}"],
            'groups_created': [],
        }

    success_count = 0
    linked_count = 0
    errors = []
    groups_created = []

    # ── Phase 1: Scan all rows into an ordered dict without touching the DB ──
    # norm_code -> list of lecturer names (order matters; duplicates are intentional)
    code_to_lecturers = OrderedDict()
    raw_code_map = {}   # norm_code -> original code string (for display / DB lookup)

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

            norm = course_code.upper().replace(' ', '')
            code_to_lecturers.setdefault(norm, []).append(lecturer_name)
            raw_code_map.setdefault(norm, course_code)

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error reading row — {e}")

    # ── Phase 2: Process each unique code ──
    for norm_code, lect_names in code_to_lecturers.items():
        orig_code = raw_code_map[norm_code]

        # Find all Course records for this code across all programmes
        courses = _find_courses(orig_code)

        # Resolve / create Lecturer objects for each name
        lecturers_resolved = []
        for lname in lect_names:
            try:
                lect = Lecturer.objects.filter(name__iexact=lname).first()
                if not lect:
                    email = _auto_email(lname)
                    if Lecturer.objects.filter(email=email).exists():
                        base = email.rsplit('@', 1)[0]
                        email = f"{base}.x@ardhi.ac.tz"
                    lect = Lecturer.objects.create(name=lname, email=email, is_full_time=True)
                    success_count += 1
                lecturers_resolved.append(lect)
            except Exception as e:
                errors.append(f"Course '{orig_code}': error resolving lecturer '{lname}' — {e}")

        if not lecturers_resolved:
            continue

        if not courses:
            errors.append(
                f"Course '{orig_code}': lecturer(s) {[l.name for l in lecturers_resolved]} saved "
                f"but course not found in DB — upload curriculum first to link"
            )
            continue

        n = len(lecturers_resolved)

        try:
            if n == 1:
                # ── Single lecturer: assign to ALL matching courses; clear stale AUTO__ groups ──
                lect = lecturers_resolved[0]
                for c in courses:
                    if c.merge_group and c.merge_group.startswith(AUTO_MERGE_PREFIX):
                        c.merge_group = None
                    c.lecturer = lect
                Course.objects.bulk_update(courses, ['lecturer', 'merge_group'])
                linked_count += len(courses)

            else:
                # ── Multiple lecturers: bin-pack by student count ──
                slug = _code_to_slug(orig_code)

                if n > len(courses):
                    errors.append(
                        f"Course '{orig_code}': {n} lecturers specified but only {len(courses)} "
                        f"course record(s) found — using first {len(courses)} lecturers"
                    )
                    lecturers_resolved = lecturers_resolved[:len(courses)]
                    n = len(lecturers_resolved)

                weighted = sorted(
                    [(c, _student_count_for(c)) for c in courses],
                    key=lambda x: x[1], reverse=True  # LPT: largest first
                )

                bins = _greedy_bin_pack(weighted, n)

                # Clear any stale AUTO__ groups for this code before writing new ones
                stale_prefix = f"{AUTO_MERGE_PREFIX}{slug}_G"
                stale_qs = Course.objects.filter(
                    merge_group__startswith=stale_prefix
                )
                stale_qs.update(merge_group=None)

                for i, (bin_items, lect) in enumerate(zip(bins, lecturers_resolved), start=1):
                    group_label = f"{AUTO_MERGE_PREFIX}{slug}_G{i}"
                    bin_courses = bin_items  # bin_items is list of Course objects from _greedy_bin_pack
                    for c in bin_courses:
                        c.merge_group = group_label
                        c.lecturer = lect
                    Course.objects.bulk_update(bin_courses, ['lecturer', 'merge_group'])
                    linked_count += len(bin_courses)
                    groups_created.append({
                        'course': orig_code,
                        'group': group_label,
                        'lecturer': lect.name,
                        'programmes': [c.programme.code for c in bin_courses],
                        'students': sum(w for c, w in weighted if c in bin_courses),
                    })

        except Exception as e:
            errors.append(f"Course '{orig_code}': error during assignment — {e}")

    return {
        'success_count': success_count,
        'linked_count': linked_count,
        'errors': errors,
        'groups_created': groups_created,
    }
