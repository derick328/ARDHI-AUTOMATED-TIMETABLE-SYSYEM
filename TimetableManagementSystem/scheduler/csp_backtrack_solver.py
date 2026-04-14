"""
Phase 3 of HGCSA: CSP with Backtracking
Guarantees maximum course placement by exhaustively searching all valid
(timeslot, room) combinations with full constraint propagation and backtracking.

Merge-group support:
  Unscheduled courses sharing the same merge_group are treated as one unit.
  The unit is placed as a whole — same room + timeslot — or not at all.

Shared-timeslot support:
  Unscheduled courses with no merge_group that share (code, study_year, semester)
  are attempted together: same timeslot, each in its own room. Falls back to
  individual placement if no common timeslot can be found.
"""
from datetime import time
from collections import defaultdict
import sys

from .greedy_solver import _try_place_shared_group, _room_order_for_course

sys.setrecursionlimit(10000)


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def _build_units(unscheduled, student_counts):
    """
    Group unscheduled courses into scheduling units:
      1. Merge-group units  — same merge_group, one room, combined count
      2. Shared-timeslot units — same (code, year, sem), no merge_group,
                                  each gets its own room
      3. True singles

    Returns (units, combined_counts) where combined_counts is keyed by the
    first course's id in each unit and holds the COMBINED count for merge
    groups, or the INDIVIDUAL count for shared-timeslot / single units.
    For shared-timeslot units each member also has its own entry in combined_counts.
    """
    # Step 1: merge groups
    merge_grouped = defaultdict(list)
    singles = []
    for c in unscheduled:
        if c.merge_group:
            merge_grouped[c.merge_group].append(c)
        else:
            singles.append(c)

    # Step 2: shared-timeslot groups among non-merge singles
    shared_buckets = defaultdict(list)
    true_singles = []
    for c in singles:
        key = (c.code, c.study_year, c.semester)
        shared_buckets[key].append(c)

    shared_groups = []
    for group in shared_buckets.values():
        if len(group) >= 2:
            shared_groups.append(group)
        else:
            true_singles.extend(group)

    # Build units list: merge groups first, then shared-timeslot, then singles
    units = (
        list(merge_grouped.values())
        + shared_groups
        + [[c] for c in true_singles]
    )

    combined_counts = {}
    for unit in units:
        if len(unit) > 1 and not unit[0].merge_group:
            # Shared-timeslot group — store individual count per course id
            for c in unit:
                combined_counts[c.id] = student_counts.get((c.programme_id, c.study_year), 0)
        else:
            # Merge group or true single — store combined / individual count under leader
            total = sum(student_counts.get((c.programme_id, c.study_year), 0) for c in unit)
            combined_counts[unit[0].id] = total

    return units, combined_counts


def csp_backtrack(unscheduled, scheduled, rooms, timeslots, student_counts):
    """
    Phase 3: Sequential greedy sweep for remaining unscheduled courses.

    Handles three unit types:
      - Merge groups        : one room + combined capacity (existing logic)
      - Shared-timeslot groups: same timeslot, individual rooms (new)
      - True singles        : independent placement (existing logic)

    Falls back to individual placement for shared-timeslot groups when no
    common timeslot can accommodate all members simultaneously.

    Returns (scheduled_list, unplaced_courses).
    """
    if not unscheduled:
        return scheduled, []

    units, combined_counts = _build_units(unscheduled, student_counts)

    # Seed occupation sets from already-placed courses
    occupied_rooms     = set()
    occupied_lecturers = set()
    occupied_groups    = set()
    for a in scheduled:
        occupied_rooms.add((a['room'].id, a['timeslot'].id))
        if a['course'].lecturer_id:
            occupied_lecturers.add((a['course'].lecturer_id, a['timeslot'].id))
        occupied_groups.add((a['course'].programme_id, a['course'].study_year, a['timeslot'].id))

    unplaced = []

    for unit in units:
        is_shared_timeslot = len(unit) > 1 and not unit[0].merge_group

        # ── Shared-timeslot group ────────────────────────────────────────────
        if is_shared_timeslot:
            result = _try_place_shared_group(
                unit, timeslots, rooms, student_counts,
                occupied_rooms, occupied_lecturers, occupied_groups,
            )
            if result is not None:
                scheduled.extend(result)
            else:
                # Fallback: try each entry independently
                for c in unit:
                    _place_single_csp(
                        c, timeslots, rooms, student_counts,
                        occupied_rooms, occupied_lecturers, occupied_groups,
                        scheduled, unplaced,
                    )
            continue

        # ── Merge group or true single ───────────────────────────────────────
        combined_count = combined_counts[unit[0].id]
        is_lab         = unit[0].is_lab
        room_order     = _room_order_for_course(unit[0], rooms)
        assigned       = False

        for timeslot in timeslots:
            if _is_friday_restricted(timeslot):
                continue

            group_keys = [(c.programme_id, c.study_year, timeslot.id) for c in unit]
            if any(gk in occupied_groups for gk in group_keys):
                continue

            lect_keys     = []
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


def _place_single_csp(c, timeslots, rooms, student_counts,
                      occupied_rooms, occupied_lecturers, occupied_groups,
                      scheduled, unplaced):
    """Place a single course independently during Phase 3."""
    sc         = student_counts.get((c.programme_id, c.study_year), 0)
    room_order = _room_order_for_course(c, rooms)
    assigned   = False

    for timeslot in timeslots:
        if _is_friday_restricted(timeslot):
            continue
        if (c.programme_id, c.study_year, timeslot.id) in occupied_groups:
            continue
        if c.lecturer_id and (c.lecturer_id, timeslot.id) in occupied_lecturers:
            continue

        for room in room_order:
            if room.capacity < sc:
                continue
            rk = (room.id, timeslot.id)
            if rk in occupied_rooms:
                continue

            occupied_rooms.add(rk)
            occupied_groups.add((c.programme_id, c.study_year, timeslot.id))
            if c.lecturer_id:
                occupied_lecturers.add((c.lecturer_id, timeslot.id))
            scheduled.append({'course': c, 'room': room, 'timeslot': timeslot})
            assigned = True
            break

        if assigned:
            break

    if not assigned:
        unplaced.append(c)
