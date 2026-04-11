"""
HGCSA — Hybrid Greedy CSP Simulated Annealing Scheduler

Orchestrates all 5 phases to produce a 100% conflict-free,
optimized university timetable.

Phase 1: Graph Coloring    — order courses by conflict degree
Phase 2: Greedy            — fast first-pass (85-95% placed)
Phase 3: CSP+Backtracking  — place remaining 5-15% (100% coverage)
Phase 4: Simulated Annealing — optimize soft constraints
Phase 5: Validation        — verify zero conflicts in final output
"""
from .graph_coloring import build_conflict_graph, sort_by_conflict_degree, validate_timetable
from .greedy_solver import greedy_assign
from .csp_backtrack_solver import csp_backtrack
from .simulated_annealing import simulated_annealing
from .models import TimetableEntry, Course, Room, Timeslot, Lecturer, StudentCount, Programme


class HGCSAScheduler:

    def run(self, programme_ids=None, semester=None, study_years=None, exam_only=False):
        """
        Run the full HGCSA pipeline.

        Args:
            programme_ids: list of Programme IDs to schedule (None = all)
            semester: 1 or 2 (None = both)
            study_years: list of years 1-4 (None = all)
            exam_only: if True, only schedule is_exam courses

        Returns:
            (entries, conflicts) — list of TimetableEntry objects and conflict list
        """
        # --- Load data from DB ---
        course_qs = Course.objects.select_related('programme', 'lecturer')
        if programme_ids:
            course_qs = course_qs.filter(programme_id__in=programme_ids)
        if semester:
            course_qs = course_qs.filter(semester=semester)
        if study_years:
            course_qs = course_qs.filter(study_year__in=study_years)
        if exam_only:
            course_qs = course_qs.filter(is_exam=True)
        else:
            course_qs = course_qs.filter(is_exam=False)

        courses = list(course_qs)
        if not courses:
            return [], []

        rooms = list(Room.objects.all())
        timeslots = list(Timeslot.objects.all())

        # Build student count lookup
        sc_qs = StudentCount.objects.all()
        if programme_ids:
            sc_qs = sc_qs.filter(programme_id__in=programme_ids)
        student_counts = {
            (sc.programme_id, sc.study_year): sc.total_count
            for sc in sc_qs
        }

        # --- Phase 1: Graph Coloring ---
        graph = build_conflict_graph(courses)
        ordered_courses = sort_by_conflict_degree(courses, graph)

        # --- Phase 2: Greedy first-pass ---
        scheduled, unscheduled = greedy_assign(ordered_courses, rooms, timeslots, student_counts)

        # --- Phase 3: CSP + Backtracking ---
        if unscheduled:
            scheduled = csp_backtrack(unscheduled, scheduled, rooms, timeslots, student_counts)

        # --- Phase 4: Simulated Annealing ---
        optimized = simulated_annealing(scheduled, rooms, timeslots, student_counts)

        # --- Save to database ---
        entries = self._save_to_db(optimized, programme_ids, semester, study_years, exam_only)

        # --- Phase 5: Graph Coloring Validation ---
        entry_objects = list(
            TimetableEntry.objects.select_related('course', 'room', 'timeslot', 'programme', 'lecturer')
            .filter(id__in=[e.id for e in entries])
        )
        conflicts = validate_timetable(entry_objects)

        return entries, conflicts

    def _save_to_db(self, assignments, programme_ids, semester, study_years, exam_only):
        """
        Clear existing entries for the specified scope and save new assignments.
        Returns list of saved TimetableEntry objects.
        """
        # Delete only entries in scope to avoid wiping unrelated timetables
        delete_qs = TimetableEntry.objects.all()
        if programme_ids:
            delete_qs = delete_qs.filter(programme_id__in=programme_ids)
        if semester:
            delete_qs = delete_qs.filter(course__semester=semester)
        if study_years:
            delete_qs = delete_qs.filter(course__study_year__in=study_years)
        delete_qs = delete_qs.filter(is_exam=exam_only)
        delete_qs.delete()

        entries = []
        for a in assignments:
            entry = TimetableEntry(
                course=a['course'],
                room=a['room'],
                timeslot=a['timeslot'],
                programme=a['course'].programme,
                lecturer=a['course'].lecturer,
                is_exam=a['course'].is_exam,
            )
            entries.append(entry)

        TimetableEntry.objects.bulk_create(entries, ignore_conflicts=False)

        # Re-fetch with IDs
        saved = list(
            TimetableEntry.objects.select_related('course', 'room', 'timeslot', 'programme', 'lecturer')
            .filter(
                course__in=[a['course'] for a in assignments]
            )
        )
        return saved
