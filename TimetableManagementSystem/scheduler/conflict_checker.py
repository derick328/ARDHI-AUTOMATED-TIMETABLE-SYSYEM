"""
Standalone conflict checker for the API endpoint.
Wraps validate_timetable from graph_coloring.py.
"""
from .models import TimetableEntry
from .graph_coloring import validate_timetable


def check_all_conflicts(programme_ids=None, semester=None, study_years=None, exam_only=None):
    """
    Run a conflict check on the current timetable entries.

    Returns:
        {
            'total_conflicts': int,
            'room_conflicts': [...],
            'lecturer_conflicts': [...],
            'student_group_conflicts': [...],
            'is_valid': bool
        }
    """
    qs = TimetableEntry.objects.select_related(
        'course', 'room', 'timeslot', 'programme', 'lecturer'
    )
    if programme_ids:
        qs = qs.filter(programme_id__in=programme_ids)
    if semester:
        qs = qs.filter(course__semester=semester)
    if study_years:
        qs = qs.filter(course__study_year__in=study_years)
    if exam_only is not None:
        qs = qs.filter(is_exam=exam_only)

    entries = list(qs)
    all_conflicts = validate_timetable(entries)

    room_conflicts = [c for c in all_conflicts if c['type'] == 'room_double_booking']
    lecturer_conflicts = [c for c in all_conflicts if c['type'] == 'lecturer_overlap']
    group_conflicts = [c for c in all_conflicts if c['type'] == 'student_group_conflict']

    return {
        'total_conflicts': len(all_conflicts),
        'room_conflicts': room_conflicts,
        'lecturer_conflicts': lecturer_conflicts,
        'student_group_conflicts': group_conflicts,
        'is_valid': len(all_conflicts) == 0,
        'entries_checked': len(entries),
    }
