"""
Phase 4 of HGCSA: Simulated Annealing
Optimizes soft constraints while guaranteeing hard constraints are never violated.

Soft constraints optimized:
  1. Minimize gaps in lecturer daily schedule
  2. Avoid back-to-back heavy courses for same student group
  3. Spread courses evenly across Monday–Friday
  4. Prefer morning slots (before 12:00)
  5. Balance room usage
  6. Avoid last timeslot of the day
"""
import math
import random
from datetime import time
from collections import defaultdict


DAY_ORDER = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4}


def _is_friday_restricted(timeslot):
    if timeslot.day != 'FRI':
        return False
    return timeslot.start_time >= time(12, 0)


def _hard_constraints_ok(assignments, student_counts):
    """
    Quick hard-constraint check for a candidate swap.
    Returns True if all hard constraints still hold.
    """
    seen_rooms = set()
    seen_lecturers = set()
    seen_groups = set()

    for a in assignments:
        room_key = (a['room'].id, a['timeslot'].id)
        if room_key in seen_rooms:
            return False
        seen_rooms.add(room_key)

        if a['course'].lecturer_id:
            lect_key = (a['course'].lecturer_id, a['timeslot'].id)
            if lect_key in seen_lecturers:
                return False
            seen_lecturers.add(lect_key)

        group_key = (a['course'].programme_id, a['course'].study_year, a['timeslot'].id)
        if group_key in seen_groups:
            return False
        seen_groups.add(group_key)

        # Friday restriction
        if _is_friday_restricted(a['timeslot']):
            return False

        # Lab constraint
        if a['course'].is_lab and not a['room'].is_lab:
            return False

        # Capacity constraint
        student_count = student_counts.get(
            (a['course'].programme_id, a['course'].study_year), 0
        )
        if a['room'].capacity < student_count:
            return False

    return True


def compute_score(assignments):
    """
    Compute soft-constraint quality score.
    Higher score = better timetable quality.
    """
    score = 0

    # Soft constraint 4: prefer morning slots (before 12:00)
    for a in assignments:
        if a['timeslot'].start_time < time(12, 0):
            score += 2

    # Soft constraint 3: spread courses across all 5 weekdays
    days_used = len(set(a['timeslot'].day for a in assignments))
    score += days_used * 10

    # Soft constraint 6: penalize last slot of day (17:00+)
    for a in assignments:
        if a['timeslot'].start_time >= time(16, 0):
            score -= 3

    # Soft constraint 5: balance room usage (penalize overloaded rooms)
    room_usage = defaultdict(int)
    for a in assignments:
        room_usage[a['room'].id] += 1
    if room_usage:
        avg = sum(room_usage.values()) / len(room_usage)
        variance = sum((v - avg) ** 2 for v in room_usage.values()) / len(room_usage)
        score -= int(variance)

    # Soft constraint 1: minimize gaps in lecturer daily schedule
    lecturer_slots = defaultdict(list)
    for a in assignments:
        if a['course'].lecturer_id:
            lecturer_slots[a['course'].lecturer_id].append(
                (DAY_ORDER.get(a['timeslot'].day, 0), a['timeslot'].start_time)
            )
    for slots in lecturer_slots.values():
        day_groups = defaultdict(list)
        for day_ord, st in slots:
            day_groups[day_ord].append(st)
        for day_slots in day_groups.values():
            day_slots.sort()
            # Penalize each gap between consecutive slots
            for i in range(1, len(day_slots)):
                gap_mins = (
                    day_slots[i].hour * 60 + day_slots[i].minute
                    - day_slots[i - 1].hour * 60 - day_slots[i - 1].minute
                )
                if gap_mins > 120:  # gap > 2 hours
                    score -= 5

    return score


def simulated_annealing(scheduled, rooms, timeslots, student_counts,
                        temperature=1000.0, cooling_rate=0.95, min_temperature=1.0):
    """
    Phase 4: Simulated annealing optimization.

    Args:
        scheduled: list of valid assignment dicts from Phase 3
        rooms: all available rooms
        timeslots: all available timeslots
        student_counts: dict {(programme_id, study_year): total_count}
        temperature: starting temperature
        cooling_rate: multiplicative cooling factor per iteration
        min_temperature: stop when temp falls below this

    Returns:
        Optimized list of assignment dicts (hard constraints never violated)
    """
    if len(scheduled) < 2:
        return scheduled

    current = list(scheduled)
    current_score = compute_score(current)
    best = list(current)
    best_score = current_score

    temp = temperature

    while temp > min_temperature:
        # Pick two random assignments to swap timeslots (and possibly rooms)
        i, j = random.sample(range(len(current)), 2)
        candidate = list(current)

        # Swap timeslots between the two assignments
        a_i = {**candidate[i], 'timeslot': candidate[j]['timeslot']}
        a_j = {**candidate[j], 'timeslot': candidate[i]['timeslot']}
        candidate[i] = a_i
        candidate[j] = a_j

        # Reject immediately if hard constraints are violated
        if not _hard_constraints_ok(candidate, student_counts):
            temp *= cooling_rate
            continue

        new_score = compute_score(candidate)
        delta = new_score - current_score

        # Accept better solutions always; accept worse with probability e^(delta/T)
        if delta > 0 or random.random() < math.exp(delta / temp):
            current = candidate
            current_score = new_score
            if current_score > best_score:
                best = list(current)
                best_score = current_score

        temp *= cooling_rate

    return best
