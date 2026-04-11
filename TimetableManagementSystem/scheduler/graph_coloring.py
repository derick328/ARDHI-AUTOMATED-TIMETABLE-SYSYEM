"""
Phase 1 & 5 of HGCSA: Graph Coloring
- Phase 1: Build conflict graph, sort courses by degree (most constrained first)
- Phase 5: Validate final timetable entries for zero conflicts
"""


def build_conflict_graph(courses):
    """
    Build an undirected conflict graph.
    Two courses conflict if they share a lecturer OR share the same
    programme+study_year (i.e. same student group).

    Returns: dict {course_id: set of conflicting course_ids}
    """
    graph = {c.id: set() for c in courses}
    course_list = list(courses)
    for i, c1 in enumerate(course_list):
        for c2 in course_list[i + 1:]:
            conflict = False
            # Shared lecturer
            if c1.lecturer_id and c1.lecturer_id == c2.lecturer_id:
                conflict = True
            # Same student group (programme + year)
            if c1.programme_id == c2.programme_id and c1.study_year == c2.study_year:
                conflict = True
            if conflict:
                graph[c1.id].add(c2.id)
                graph[c2.id].add(c1.id)
    return graph


def sort_by_conflict_degree(courses, graph):
    """
    Sort courses in descending order of conflict degree.
    Courses with more conflicts are scheduled first — they are harder to place.
    """
    return sorted(courses, key=lambda c: len(graph.get(c.id, set())), reverse=True)


def validate_timetable(entries):
    """
    Phase 5: Final validation of timetable entries.
    Checks for:
      1. Room double-booking (same room, same timeslot)
      2. Lecturer overlap (same lecturer, same timeslot)
      3. Student group conflict (same programme+year, same timeslot)

    entries: queryset or list of TimetableEntry objects (with select_related loaded)
    Returns: list of conflict dicts, empty list = 100% valid
    """
    conflicts = []
    seen_room_timeslot = {}      # (room_id, timeslot_id) -> entry_id
    seen_lecturer_timeslot = {}  # (lecturer_id, timeslot_id) -> entry_id
    seen_group_timeslot = {}     # (programme_id, study_year, timeslot_id) -> entry_id

    for entry in entries:
        # Hard constraint 1: no room double-booking
        room_key = (entry.room_id, entry.timeslot_id)
        if room_key in seen_room_timeslot:
            conflicts.append({
                'type': 'room_double_booking',
                'room': entry.room.name,
                'timeslot': str(entry.timeslot),
                'entry1_id': seen_room_timeslot[room_key],
                'entry2_id': entry.id,
                'entry1_course': '',
                'entry2_course': entry.course.code,
            })
        else:
            seen_room_timeslot[room_key] = entry.id

        # Hard constraint 2: no lecturer overlap
        if entry.lecturer_id:
            lect_key = (entry.lecturer_id, entry.timeslot_id)
            if lect_key in seen_lecturer_timeslot:
                conflicts.append({
                    'type': 'lecturer_overlap',
                    'lecturer': entry.lecturer.name,
                    'timeslot': str(entry.timeslot),
                    'entry1_id': seen_lecturer_timeslot[lect_key],
                    'entry2_id': entry.id,
                    'entry2_course': entry.course.code,
                })
            else:
                seen_lecturer_timeslot[lect_key] = entry.id

        # Hard constraint 3: no student group conflict
        group_key = (entry.programme_id, entry.course.study_year, entry.timeslot_id)
        if group_key in seen_group_timeslot:
            conflicts.append({
                'type': 'student_group_conflict',
                'programme': entry.programme.code,
                'study_year': entry.course.study_year,
                'timeslot': str(entry.timeslot),
                'entry1_id': seen_group_timeslot[group_key],
                'entry2_id': entry.id,
                'entry2_course': entry.course.code,
            })
        else:
            seen_group_timeslot[group_key] = entry.id

    return conflicts
