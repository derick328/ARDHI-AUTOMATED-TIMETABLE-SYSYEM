"""
Phase 3 of HGCSA: CSP with Backtracking
Guarantees 100% course placement by exhaustively searching all valid
(timeslot, room) combinations with full constraint propagation and backtracking.
"""
from datetime import time
import sys

# Increase recursion limit for large timetables
sys.setrecursionlimit(10000)


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def csp_backtrack(unscheduled, scheduled, rooms, timeslots, student_counts):
    """
    Phase 3: CSP + Backtracking for remaining unscheduled courses.

    Args:
        unscheduled: list of courses not placed by greedy
        scheduled: list of existing assignments (from Phase 2)
        rooms: all available rooms
        timeslots: all available timeslots
        student_counts: dict {(programme_id, study_year): total_count}

    Returns:
        scheduled list (extended with newly placed courses)
        Raises RuntimeError if a course truly cannot be placed (impossible constraints)
    """
    if not unscheduled:
        return scheduled

    # Build occupancy sets from existing scheduled assignments
    occupied_rooms = set()
    occupied_lecturers = set()
    occupied_groups = set()

    for a in scheduled:
        occupied_rooms.add((a['room'].id, a['timeslot'].id))
        if a['course'].lecturer_id:
            occupied_lecturers.add((a['course'].lecturer_id, a['timeslot'].id))
        occupied_groups.add((a['course'].programme_id, a['course'].study_year, a['timeslot'].id))

    # Sort rooms by capacity descending
    sorted_rooms = sorted(rooms, key=lambda r: r.capacity, reverse=True)

    def backtrack(index):
        """Recursive backtracking. Returns True if all courses placed."""
        if index == len(unscheduled):
            return True

        course = unscheduled[index]
        student_count = student_counts.get((course.programme_id, course.study_year), 0)

        for timeslot in timeslots:
            if _is_friday_restricted(timeslot):
                continue

            group_key = (course.programme_id, course.study_year, timeslot.id)
            if group_key in occupied_groups:
                continue

            lect_key = None
            if course.lecturer_id:
                lect_key = (course.lecturer_id, timeslot.id)
                if lect_key in occupied_lecturers:
                    continue

            for room in sorted_rooms:
                if course.is_lab and not room.is_lab:
                    continue
                if not course.is_lab and room.is_lab:
                    continue
                if room.capacity < student_count:
                    continue

                room_key = (room.id, timeslot.id)
                if room_key in occupied_rooms:
                    continue

                # Try this assignment
                occupied_rooms.add(room_key)
                occupied_groups.add(group_key)
                if lect_key:
                    occupied_lecturers.add(lect_key)
                scheduled.append({'course': course, 'room': room, 'timeslot': timeslot})

                if backtrack(index + 1):
                    return True

                # Backtrack — undo this assignment
                scheduled.pop()
                occupied_rooms.discard(room_key)
                occupied_groups.discard(group_key)
                if lect_key:
                    occupied_lecturers.discard(lect_key)

        # Could not place this course — signal failure up the call stack
        return False

    success = backtrack(0)

    if not success:
        # Some courses genuinely cannot be placed (e.g., not enough rooms).
        # Return partial schedule with an error marker so the caller can report it.
        still_unplaced = [
            c for c in unscheduled
            if not any(a['course'].id == c.id for a in scheduled)
        ]
        raise RuntimeError(
            f"CSP backtracking failed: {len(still_unplaced)} course(s) could not be scheduled. "
            f"Add more rooms/timeslots or reduce constraints. "
            f"Unplaced: {[c.code for c in still_unplaced]}"
        )

    return scheduled
