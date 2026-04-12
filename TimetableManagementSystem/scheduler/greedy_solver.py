"""
Phase 2 of HGCSA: Greedy Solver
Fast first-pass assignment targeting 85-95% of courses.
All hard constraints are enforced during assignment.

Merge-group support:
  Courses that share the same non-null merge_group are treated as one unit.
  They receive the same room + timeslot, and room capacity is checked against
  the COMBINED student count of all courses in the group.
"""
from datetime import time
from collections import defaultdict


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def _build_merge_groups(ordered_courses, student_counts):
    """
    Partition courses into:
      - groups:  list of lists, each inner list = courses sharing a merge_group
      - singles: list of courses with no merge_group (scheduled individually)

    Returns (units, combined_counts) where:
      units          = list of course-lists (length 1 for singles)
      combined_counts = dict {group_leader_id: combined_student_count}
    """
    grouped = defaultdict(list)
    singles = []
    for c in ordered_courses:
        if c.merge_group:
            grouped[c.merge_group].append(c)
        else:
            singles.append(c)

    units = []
    combined_counts = {}

    # Add merge groups first (they are harder to place — need bigger rooms)
    for group_courses in grouped.values():
        units.append(group_courses)
        total = sum(
            student_counts.get((c.programme_id, c.study_year), 0)
            for c in group_courses
        )
        leader_id = group_courses[0].id
        combined_counts[leader_id] = total

    # Then singles
    for c in singles:
        units.append([c])
        combined_counts[c.id] = student_counts.get((c.programme_id, c.study_year), 0)

    return units, combined_counts


def _room_list_for_unit(is_lab, rooms):
    """
    Return rooms in preference order for a unit:
      - Lab courses  : lab rooms only (by capacity desc)
      - Non-lab courses: non-lab rooms first, then lab rooms as overflow
        (lab rooms are never wasted — they can host regular lectures if needed)
    """
    lab_rooms     = sorted([r for r in rooms if r.is_lab],     key=lambda r: r.capacity, reverse=True)
    non_lab_rooms = sorted([r for r in rooms if not r.is_lab], key=lambda r: r.capacity, reverse=True)
    if is_lab:
        return lab_rooms
    return non_lab_rooms + lab_rooms   # prefer non-lab, fall back to lab


def greedy_assign(ordered_courses, rooms, timeslots, student_counts):
    """
    Phase 2: Greedy first-pass assignment.
    Supports merge groups — courses sharing the same merge_group value
    are assigned the same room + timeslot (combined student count used).

    Non-lab courses try non-lab rooms first; if none fit they overflow into
    lab rooms so that large lab spaces are never left idle.

    Returns:
        scheduled: list of assignment dicts {'course', 'room', 'timeslot'}
        unscheduled: list of courses that could not be placed
    """
    scheduled = []
    unscheduled = []

    occupied_rooms = set()       # (room_id, timeslot_id)
    occupied_lecturers = set()   # (lecturer_id, timeslot_id)
    occupied_groups = set()      # (programme_id, study_year, timeslot_id)

    units, combined_counts = _build_merge_groups(ordered_courses, student_counts)

    for unit in units:
        leader = unit[0]
        combined_count = combined_counts[leader.id]
        is_lab = leader.is_lab
        room_order = _room_list_for_unit(is_lab, rooms)

        assigned = False

        for timeslot in timeslots:
            if _is_friday_restricted(timeslot):
                continue

            # Check all courses in the unit have free student-group slots
            group_keys = [
                (c.programme_id, c.study_year, timeslot.id) for c in unit
            ]
            if any(gk in occupied_groups for gk in group_keys):
                continue

            # Check lecturer availability for all courses in unit
            lect_keys = []
            lect_conflict = False
            for c in unit:
                if c.lecturer_id:
                    lk = (c.lecturer_id, timeslot.id)
                    if lk in occupied_lecturers:
                        lect_conflict = True
                        break
                    lect_keys.append(lk)
            if lect_conflict:
                continue

            for room in room_order:
                # Room must fit the COMBINED student count
                if room.capacity < combined_count:
                    continue

                room_key = (room.id, timeslot.id)
                if room_key in occupied_rooms:
                    continue

                # Valid slot — record assignment for every course in unit
                occupied_rooms.add(room_key)
                for gk in group_keys:
                    occupied_groups.add(gk)
                for lk in lect_keys:
                    occupied_lecturers.add(lk)

                for c in unit:
                    scheduled.append({'course': c, 'room': room, 'timeslot': timeslot})

                assigned = True
                break

            if assigned:
                break

        if not assigned:
            unscheduled.extend(unit)

    return scheduled, unscheduled
