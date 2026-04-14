"""
Phase 2 of HGCSA: Greedy Solver
Fast first-pass assignment targeting 85-95% of courses.
All hard constraints are enforced during assignment.

Merge-group support:
  Courses that share the same non-null merge_group are treated as one unit.
  They receive the same room + timeslot, and room capacity is checked against
  the COMBINED student count of all courses in the group.

Shared-timeslot support:
  Courses with no merge_group that share the same (code, study_year, semester)
  are scheduled at the SAME timeslot but each gets its OWN room sized for its
  own programme's student count.  This prevents the same course from being
  scattered across many timeslots and relieves pressure on large rooms.
"""
from datetime import time
from collections import defaultdict


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def _room_order_for_course(c, rooms):
    """Return rooms in preference order for a single course."""
    lab_rooms     = sorted([r for r in rooms if r.is_lab],     key=lambda r: r.capacity, reverse=True)
    non_lab_rooms = sorted([r for r in rooms if not r.is_lab], key=lambda r: r.capacity, reverse=True)
    return lab_rooms if c.is_lab else non_lab_rooms + lab_rooms


def _build_merge_groups(ordered_courses, student_counts):
    """
    Partition courses into merge-group units and a flat singles list.

    Returns:
      merge_units    — list of lists (each inner list shares a merge_group)
      singles_flat   — flat list of Course objects with no merge_group
      combined_counts — dict {leader_course_id: combined_student_count}
                        (only populated for merge-group leaders)
    """
    grouped = defaultdict(list)
    singles_flat = []
    for c in ordered_courses:
        if c.merge_group:
            grouped[c.merge_group].append(c)
        else:
            singles_flat.append(c)

    merge_units = []
    combined_counts = {}
    for group_courses in grouped.values():
        merge_units.append(group_courses)
        total = sum(
            student_counts.get((c.programme_id, c.study_year), 0)
            for c in group_courses
        )
        combined_counts[group_courses[0].id] = total

    return merge_units, singles_flat, combined_counts


def _build_shared_timeslot_groups(singles_flat, student_counts):
    """
    Among courses with no merge_group, group those sharing
    (code, study_year, semester). Groups of 2+ become shared-timeslot units;
    true singles remain as individual [course] lists.

    Returns:
      shared_units — list of lists, each with 2+ courses (same code/year/sem)
      single_units — list of [course] lists (one entry per list)
    """
    buckets = defaultdict(list)
    for c in singles_flat:
        key = (c.code, c.study_year, c.semester)
        buckets[key].append(c)

    shared_units = []
    single_units = []
    for group in buckets.values():
        if len(group) >= 2:
            # Largest student count first — hardest-to-room entry picked first
            group.sort(
                key=lambda c: student_counts.get((c.programme_id, c.study_year), 0),
                reverse=True,
            )
            shared_units.append(group)
        else:
            single_units.append(group)

    # Most-programme groups first (most constrained)
    shared_units.sort(key=lambda g: len(g), reverse=True)
    return shared_units, single_units


def _try_place_shared_group(group, timeslots, rooms, student_counts,
                             occupied_rooms, occupied_lecturers, occupied_groups):
    """
    Try to place all entries in a shared-timeslot group at the same timeslot,
    giving each entry its own appropriately-sized room.

    Returns a list of assignment dicts on success, or None if no timeslot works
    for the whole group simultaneously.
    """
    for timeslot in timeslots:
        if _is_friday_restricted(timeslot):
            continue

        candidate_rooms = {}   # course.id → Room
        temp_rooms      = set()  # rooms tentatively claimed in this attempt
        all_ok          = True

        for c in group:
            sc = student_counts.get((c.programme_id, c.study_year), 0)

            # Student-group conflict?
            if (c.programme_id, c.study_year, timeslot.id) in occupied_groups:
                all_ok = False
                break

            # Lecturer conflict?
            if c.lecturer_id and (c.lecturer_id, timeslot.id) in occupied_lecturers:
                all_ok = False
                break

            # Find the best available room for this single entry
            found = None
            for room in _room_order_for_course(c, rooms):
                if room.capacity < sc:
                    continue
                rk = (room.id, timeslot.id)
                if rk in occupied_rooms or rk in temp_rooms:
                    continue
                found = room
                temp_rooms.add(rk)
                break

            if found is None:
                all_ok = False
                break

            candidate_rooms[c.id] = found

        if all_ok:
            # Commit all entries to the chosen timeslot
            assignments = []
            for c in group:
                room = candidate_rooms[c.id]
                occupied_rooms.add((room.id, timeslot.id))
                occupied_groups.add((c.programme_id, c.study_year, timeslot.id))
                if c.lecturer_id:
                    occupied_lecturers.add((c.lecturer_id, timeslot.id))
                assignments.append({'course': c, 'room': room, 'timeslot': timeslot})
            return assignments

    return None  # no timeslot could accommodate the whole group


def _place_single(c, timeslots, rooms, student_counts,
                  occupied_rooms, occupied_lecturers, occupied_groups,
                  scheduled, unscheduled):
    """Place a single course entry independently (fallback / true-single path)."""
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
        unscheduled.append(c)


def greedy_assign(ordered_courses, rooms, timeslots, student_counts):
    """
    Phase 2: Greedy first-pass assignment.

    Scheduling order (most-constrained first):
      1. Merge-group units  — same room + same timeslot, combined capacity check
      2. Shared-timeslot groups — same timeslot, each entry gets its own room
      3. True singles       — scheduled independently

    For shared-timeslot groups: if no single timeslot can accommodate ALL
    entries simultaneously, falls back to scheduling each entry independently
    so that the maximum number of courses are placed.

    Returns:
        scheduled:   list of assignment dicts {'course', 'room', 'timeslot'}
        unscheduled: list of courses that could not be placed
    """
    scheduled   = []
    unscheduled = []

    occupied_rooms     = set()   # (room_id, timeslot_id)
    occupied_lecturers = set()   # (lecturer_id, timeslot_id)
    occupied_groups    = set()   # (programme_id, study_year, timeslot_id)

    merge_units, singles_flat, combined_counts = _build_merge_groups(
        ordered_courses, student_counts
    )

    # ── 1. Merge-group units (same room + timeslot, combined capacity) ──────
    for unit in merge_units:
        leader        = unit[0]
        combined_count = combined_counts[leader.id]
        room_order    = _room_order_for_course(leader, rooms)
        assigned      = False

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

    # ── 2. Shared-timeslot groups (same timeslot, individual rooms) ──────────
    shared_units, single_units = _build_shared_timeslot_groups(
        singles_flat, student_counts
    )

    for group in shared_units:
        result = _try_place_shared_group(
            group, timeslots, rooms, student_counts,
            occupied_rooms, occupied_lecturers, occupied_groups,
        )
        if result is not None:
            scheduled.extend(result)
        else:
            # Fallback: schedule each entry individually
            for c in group:
                _place_single(
                    c, timeslots, rooms, student_counts,
                    occupied_rooms, occupied_lecturers, occupied_groups,
                    scheduled, unscheduled,
                )

    # ── 3. True singles ───────────────────────────────────────────────────────
    for unit in single_units:
        _place_single(
            unit[0], timeslots, rooms, student_counts,
            occupied_rooms, occupied_lecturers, occupied_groups,
            scheduled, unscheduled,
        )

    return scheduled, unscheduled
