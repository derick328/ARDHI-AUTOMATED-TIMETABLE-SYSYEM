"""
Phase 2 of HGCSA: Greedy Solver
Fast first-pass assignment targeting 85-95% of courses.
All hard constraints are enforced during assignment.
"""
from datetime import time


def _is_friday_restricted(timeslot):
    """
    Friday restriction: only allow slots ending by 12:00.
    Afternoon slots on Friday are blocked.
    """
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def greedy_assign(ordered_courses, rooms, timeslots, student_counts):
    """
    Phase 2: Greedy first-pass assignment.

    Args:
        ordered_courses: courses sorted by conflict degree (highest first)
        rooms: list of Room objects
        timeslots: list of Timeslot objects
        student_counts: dict {(programme_id, study_year): total_count}

    Returns:
        scheduled: list of assignment dicts {'course', 'room', 'timeslot'}
        unscheduled: list of courses that could not be placed
    """
    scheduled = []
    unscheduled = []

    # Tracking sets for hard constraint enforcement
    occupied_rooms = set()      # (room_id, timeslot_id)
    occupied_lecturers = set()  # (lecturer_id, timeslot_id)
    occupied_groups = set()     # (programme_id, study_year, timeslot_id)

    # Sort rooms by capacity descending — try larger rooms first for better fit
    sorted_rooms = sorted(rooms, key=lambda r: r.capacity, reverse=True)

    for course in ordered_courses:
        student_count = student_counts.get((course.programme_id, course.study_year), 0)
        assigned = False

        for timeslot in timeslots:
            # Hard constraint 6: Friday restrictions
            if _is_friday_restricted(timeslot):
                continue

            # Hard constraint 3: no student group conflict
            group_key = (course.programme_id, course.study_year, timeslot.id)
            if group_key in occupied_groups:
                continue

            # Hard constraint 2: no lecturer overlap
            lect_key = None
            if course.lecturer_id:
                lect_key = (course.lecturer_id, timeslot.id)
                if lect_key in occupied_lecturers:
                    continue

            for room in sorted_rooms:
                # Hard constraint 5: lab courses only in lab rooms
                if course.is_lab and not room.is_lab:
                    continue
                # Non-lab courses should not use lab rooms unnecessarily
                if not course.is_lab and room.is_lab:
                    continue

                # Hard constraint 4: room capacity >= student count
                if room.capacity < student_count:
                    continue

                # Hard constraint 1: no room double-booking
                room_key = (room.id, timeslot.id)
                if room_key in occupied_rooms:
                    continue

                # Valid assignment found — record it
                occupied_rooms.add(room_key)
                occupied_groups.add(group_key)
                if lect_key:
                    occupied_lecturers.add(lect_key)

                scheduled.append({
                    'course': course,
                    'room': room,
                    'timeslot': timeslot,
                })
                assigned = True
                break

            if assigned:
                break

        if not assigned:
            unscheduled.append(course)

    return scheduled, unscheduled
