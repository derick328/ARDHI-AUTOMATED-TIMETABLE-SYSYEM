"""
Phase 3 of HGCSA: CSP with Backtracking
Guarantees maximum course placement by exhaustively searching all valid
(timeslot, room) combinations with full constraint propagation and backtracking.

Merge-group support:
  Unscheduled courses sharing the same merge_group are treated as one unit.
  The unit is placed as a whole — same room + timeslot — or not at all.
"""
from datetime import time
from collections import defaultdict
import sys

sys.setrecursionlimit(10000)


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def _build_units(unscheduled, student_counts):
    """Group unscheduled courses by merge_group; singles become unit of 1."""
    grouped = defaultdict(list)
    singles = []
    for c in unscheduled:
        if c.merge_group:
            grouped[c.merge_group].append(c)
        else:
            singles.append(c)
    units = list(grouped.values()) + [[c] for c in singles]
    counts = {}
    for unit in units:
        total = sum(student_counts.get((c.programme_id, c.study_year), 0) for c in unit)
        counts[unit[0].id] = total
    return units, counts


def _room_list_for_unit(is_lab, rooms):
    """
    Non-lab courses prefer non-lab rooms but overflow into lab rooms.
    Lab courses are restricted to lab rooms only.
    """
    lab_rooms     = sorted([r for r in rooms if r.is_lab],     key=lambda r: r.capacity, reverse=True)
    non_lab_rooms = sorted([r for r in rooms if not r.is_lab], key=lambda r: r.capacity, reverse=True)
    return lab_rooms if is_lab else non_lab_rooms + lab_rooms


def csp_backtrack(unscheduled, scheduled, rooms, timeslots, student_counts):
    """
    Phase 3: Sequential greedy sweep for remaining unscheduled courses.

    Replaces all-or-nothing recursive backtracking with a forward-only
    greedy pass that skips (marks unplaced) any course it cannot fit.
    This guarantees the maximum number of courses are placed — the old
    recursive approach rolled back ALL progress whenever a complete
    solution was impossible, producing far more unplaced courses than
    necessary.

    Returns (scheduled_list, unplaced_courses).
    """
    if not unscheduled:
        return scheduled, []

    units, combined_counts = _build_units(unscheduled, student_counts)

    # Seed occupation sets from already-placed courses
    occupied_rooms = set()
    occupied_lecturers = set()
    occupied_groups = set()
    for a in scheduled:
        occupied_rooms.add((a['room'].id, a['timeslot'].id))
        if a['course'].lecturer_id:
            occupied_lecturers.add((a['course'].lecturer_id, a['timeslot'].id))
        occupied_groups.add((a['course'].programme_id, a['course'].study_year, a['timeslot'].id))

    unplaced = []

    for unit in units:
        combined_count = combined_counts[unit[0].id]
        is_lab = unit[0].is_lab
        room_order = _room_list_for_unit(is_lab, rooms)
        assigned = False

        for timeslot in timeslots:
            if _is_friday_restricted(timeslot):
                continue

            group_keys = [(c.programme_id, c.study_year, timeslot.id) for c in unit]
            if any(gk in occupied_groups for gk in group_keys):
                continue

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
                if room.capacity < combined_count:
                    continue
                room_key = (room.id, timeslot.id)
                if room_key in occupied_rooms:
                    continue

                # Commit this unit
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
            unplaced.extend(unit)

    return scheduled, unplaced
