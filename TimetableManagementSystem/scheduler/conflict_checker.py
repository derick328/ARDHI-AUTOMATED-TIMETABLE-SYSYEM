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
    entry_map = {e.id: e for e in entries}
    all_conflicts = validate_timetable(entries)

    def _timeslot_str(c, entry_map):
        e = entry_map.get(c.get('entry1_id'))
        if e and e.timeslot:
            return f"{e.timeslot.day} {e.timeslot.start_time.strftime('%H:%M')}"
        return str(c.get('timeslot', ''))

    def _entry_course(c, entry_map, key='entry1_id'):
        e = entry_map.get(c.get(key))
        return e.course.code if e else '?'

    def _build_message(c, entry_map):
        ts = _timeslot_str(c, entry_map)
        c1 = _entry_course(c, entry_map, 'entry1_id')
        c2 = _entry_course(c, entry_map, 'entry2_id') or c.get('entry2_course', '?')
        if c['type'] == 'room_double_booking':
            e = entry_map.get(c.get('entry1_id'))
            room = e.room.name if e and e.room else '?'
            return f"Room double-booking: {room} at {ts} — {c1} and {c2}"
        if c['type'] == 'lecturer_overlap':
            return f"Lecturer conflict: {c.get('lecturer','?')} at {ts} — teaching {c1} and {c2} simultaneously"
        if c['type'] == 'student_group_conflict':
            return f"Student group conflict: [{c.get('programme','?')}] Year {c.get('study_year','?')} at {ts} — {c1} and {c2} overlap"
        return str(c)

    for c in all_conflicts:
        c['message'] = _build_message(c, entry_map)

    room_conflicts = [c for c in all_conflicts if c['type'] == 'room_double_booking']
    lecturer_conflicts = [c for c in all_conflicts if c['type'] == 'lecturer_overlap']
    group_conflicts = [c for c in all_conflicts if c['type'] == 'student_group_conflict']

    return {
        'total_conflicts': len(all_conflicts),
        'conflicts': all_conflicts,
        'room_conflicts': room_conflicts,
        'lecturer_conflicts': lecturer_conflicts,
        'student_group_conflicts': group_conflicts,
        'is_valid': len(all_conflicts) == 0,
        'entries_checked': len(entries),
    }
