"""
Upload parser for Lecturer/Course-Assignment Excel file.
Single-sheet .xlsx with 2 columns:
  Course_Code, Lecturer_Name
Column names are flexible — uses alias matching.

Behaviour when a course code appears N times with N different lecturers:

  Case A — N ≤ number of DB course records (multi-programme shared course):
    Courses are bin-packed by student count into N balanced groups.
    Each group gets one lecturer and an AUTO__CODE_Gi merge_group label
    so the scheduler places all programmes in that group into the same venue.

  Case B — N > number of DB course records (large single-programme class):
    The course is split into N sections.  The base record (section='') gets
    the first lecturer.  Extra records (section='B','C',…) are auto-created
    as copies of the base with the remaining lecturers.  Each section is
    scheduled independently in its own room.

On re-upload the stale AUTO__ merge groups and stale section records are
cleared before new assignments are written.
"""
import math
import re
import string
from collections import OrderedDict
import openpyxl
from .models import Course, Lecturer, StudentCount

COLUMN_ALIASES = {
    'course_code':   ['course_code', 'code', 'course code', 'subject_code', 'module_code', 'coursecode'],
    'lecturer_name': ['lecture_name', 'lecturer_name', 'lecture name', 'lecturer name',
                      'Lecture Name', 'Lecturer Name', 'name', 'lecturer', 'staff_name', 'instructor', 'teacher'],
}

AUTO_MERGE_PREFIX = "AUTO__"
# Section letters for auto-created splits: base='', then 'B','C','D',…
_SECTION_LETTERS = [''] + list(string.ascii_uppercase[1:])   # 25 extras max


def _normalize(value):
    if not value and value != 0:
        return ''
    s = str(value).strip().lower()
    s = re.sub(r'[\s_]+', '_', s)
    s = re.sub(r'[^\w]', '', s)
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
    slug = re.sub(r'[^a-z0-9]+', '.', name.lower().strip()).strip('.')
    return f"{slug}@ardhi.ac.tz"


def _code_to_slug(code: str) -> str:
    slug = re.sub(r'[\s\-]+', '_', code.strip().upper())
    return re.sub(r'[^\w]', '', slug)


def _greedy_bin_pack(items_with_weights, n_bins):
    """LPT bin-packing: minimise max bin weight."""
    bins = [[] for _ in range(n_bins)]
    totals = [0] * n_bins
    for item, weight in items_with_weights:
        i = totals.index(min(totals))
        bins[i].append(item)
        totals[i] += weight
    return bins


def _find_base_courses(code):
    """Return all base (section='') Course records matching a code, across all programmes."""
    qs = Course.objects.filter(code__iexact=code, section='').select_related('programme')
    if not qs.exists():
        qs = Course.objects.filter(
            code__iexact=code.replace(' ', ''), section=''
        ).select_related('programme')
    if not qs.exists():
        qs = Course.objects.filter(
            code__iexact=re.sub(r'\s+', '', code), section=''
        ).select_related('programme')
    return list(qs)


def _student_count_for(course):
    sc = StudentCount.objects.filter(
        programme=course.programme, study_year=course.study_year
    ).first()
    return sc.total_count if sc else 0


def _section_letter(idx):
    """Return the section label for index idx (0 = base = '', 1 = 'B', 2 = 'C', …)."""
    if idx < len(_SECTION_LETTERS):
        return _SECTION_LETTERS[idx]
    return f'S{idx}'


def parse_lecturers(file_obj):
    """
    Parse a course-lecturer assignment Excel file and assign lecturers to courses.

    Returns:
        {
          'success_count': int,       # new Lecturer records created
          'linked_count':  int,       # Course records updated/created
          'errors':        [str],     # hard failures
          'warnings':      [str],     # soft notes (no action needed)
          'groups_created': [dict],   # merge groups or sections that were formed
        }
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {'success_count': 0, 'linked_count': 0,
                'errors': [f"Cannot open file: {e}"], 'warnings': [], 'groups_created': []}

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {'success_count': 0, 'linked_count': 0,
                'errors': ['File is empty'], 'warnings': [], 'groups_created': []}

    headers = rows[0]
    col_map = _detect_columns(headers)

    required = ['course_code', 'lecturer_name']
    missing = [r for r in required if r not in col_map]
    if missing:
        return {
            'success_count': 0, 'linked_count': 0,
            'errors': [f"Missing required columns: {missing}. Found: {list(headers)}"],
            'warnings': [], 'groups_created': [],
        }

    success_count = 0
    linked_count = 0
    errors = []
    warnings = []
    groups_created = []

    # ── Phase 1: Scan all rows — build code → [lecturer_name, …] map ──────────
    code_to_lecturers = OrderedDict()   # norm_code → [names in order]
    raw_code_map = {}                   # norm_code → original code string

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

    # ── Phase 2: Process each unique code ─────────────────────────────────────
    for norm_code, lect_names in code_to_lecturers.items():
        orig_code = raw_code_map[norm_code]

        # Find base (section='') course records for this code
        courses = _find_base_courses(orig_code)

        # Resolve / auto-create Lecturer objects
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
            warnings.append(
                f"Course '{orig_code}': lecturer(s) {[l.name for l in lecturers_resolved]} saved "
                f"but course not found in DB — upload curriculum first to link"
            )
            continue

        n = len(lecturers_resolved)

        try:
            slug = _code_to_slug(orig_code)
            prog_ids = [c.programme_id for c in courses]

            # ── Always clean up stale AUTO__ merge groups for this code ──
            stale_prefix = f"{AUTO_MERGE_PREFIX}{slug}_G"
            Course.objects.filter(merge_group__startswith=stale_prefix).update(merge_group=None)

            # ── Always clean up stale auto-created sections for this code ──
            Course.objects.filter(
                code__iexact=orig_code, programme_id__in=prog_ids
            ).exclude(section='').delete()

            if n == 1:
                # ── Single lecturer: assign to ALL base courses ──────────────
                lect = lecturers_resolved[0]
                for c in courses:
                    c.lecturer = lect
                    c.merge_group = None
                Course.objects.bulk_update(courses, ['lecturer', 'merge_group'])
                linked_count += len(courses)

            elif n <= len(courses):
                # ── Case A: bin-pack across programmes ──────────────────────
                weighted = sorted(
                    [(c, _student_count_for(c)) for c in courses],
                    key=lambda x: x[1], reverse=True
                )
                bins = _greedy_bin_pack(weighted, n)
                for i, (bin_items, lect) in enumerate(zip(bins, lecturers_resolved), start=1):
                    group_label = f"{AUTO_MERGE_PREFIX}{slug}_G{i}"
                    for c in bin_items:
                        c.merge_group = group_label
                        c.lecturer = lect
                    Course.objects.bulk_update(bin_items, ['lecturer', 'merge_group'])
                    linked_count += len(bin_items)
                    groups_created.append({
                        'course': orig_code,
                        'type': 'merge',
                        'group': group_label,
                        'lecturer': lect.name,
                        'programmes': [c.programme.code for c in bin_items],
                        'students': sum(w for c, w in weighted if c in bin_items),
                    })

            else:
                # ── Case B: more lecturers than programmes ───────────────────
                # Split lecturers into len(courses) chunks; each base course
                # gets one chunk.  First lecturer in each chunk keeps the base
                # record (section=''); extras get new section records.
                chunk_size = math.ceil(n / len(courses))
                chunks = [
                    lecturers_resolved[i: i + chunk_size]
                    for i in range(0, n, chunk_size)
                ]

                for base_course, chunk in zip(courses, chunks):
                    for j, lect in enumerate(chunk):
                        sec = _section_letter(j)
                        if sec == '':
                            # Update the base record
                            base_course.lecturer = lect
                            base_course.merge_group = None
                            base_course.save(update_fields=['lecturer', 'merge_group'])
                        else:
                            # Create a new section record copied from the base
                            Course.objects.update_or_create(
                                code=base_course.code,
                                programme=base_course.programme,
                                section=sec,
                                defaults={
                                    'title': base_course.title,
                                    'study_year': base_course.study_year,
                                    'semester': base_course.semester,
                                    'is_exam': base_course.is_exam,
                                    'is_lab': base_course.is_lab,
                                    'lecturer': lect,
                                    'merge_group': None,
                                }
                            )
                        linked_count += 1

                    section_labels = [_section_letter(j) or 'base' for j in range(len(chunk))]
                    groups_created.append({
                        'course': orig_code,
                        'type': 'section',
                        'group': f"{base_course.programme.code} sections: "
                                 + ', '.join(
                                     base_course.code + (f' ({s})' if s != 'base' else '')
                                     for s in section_labels
                                 ),
                        'lecturer': ', '.join(l.name for l in chunk),
                        'programmes': [base_course.programme.code],
                        'students': _student_count_for(base_course),
                    })

        except Exception as e:
            errors.append(f"Course '{orig_code}': error during assignment — {e}")

    return {
        'success_count': success_count,
        'linked_count': linked_count,
        'errors': errors,
        'warnings': warnings,
        'groups_created': groups_created,
    }
