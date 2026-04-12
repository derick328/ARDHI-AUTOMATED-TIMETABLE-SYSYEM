from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token

from .models import (
    School, Programme, Lecturer, Room, Timeslot,
    Course, StudentCount, TimetableEntry,
    Stakeholder, AuditLog, UploadedCourseAssignment
)
from .serializers import (
    SchoolSerializer, ProgrammeSerializer, LecturerSerializer,
    RoomSerializer, TimeslotSerializer, CourseSerializer,
    StudentCountSerializer, TimetableEntrySerializer,
    StakeholderSerializer, AuditLogSerializer,
    UserSerializer, UserCreateSerializer
)
from .permissions import (
    IsAdminUser, IsCoordinatorOrAdmin, IsExamOfficer,
    IsExamOfficerOrCoordinatorOrAdmin, IsStakeholderOrAbove
)
from .audit_log import log_action
from .notifications import (
    notify_timetable_generated, notify_schedule_changed,
    notify_entry_deleted, get_lecturer_emails_for_entry
)
from .hgcsa_scheduler import HGCSAScheduler
from .conflict_checker import check_all_conflicts
from .timetable_export import export_excel, export_pdf
from .room_upload import parse_rooms
from .lecturer_upload import parse_lecturers
from .curriculum_parser import parse_curriculum
from .student_population_upload import parse_student_populations
from .course_assignment_upload import parse_course_assignments


# ── Helper ──────────────────────────────────────────────────────────────────────

def _get_user_role(user):
    if not user.is_authenticated:
        return 'public'
    if user.is_superuser:
        return 'admin'
    try:
        return user.stakeholder.role
    except Exception:
        return 'unknown'


def _redirect_by_role(user):
    role = _get_user_role(user)
    mapping = {
        'admin': 'admin_dashboard',
        'TTC': 'coordinator',
        'HOD': 'coordinator',
        'EXAM': 'exam_officer',
        'DUP': 'stakeholder',
        'DEAN': 'stakeholder',
        'ICTD': 'stakeholder',
    }
    return redirect(mapping.get(role, 'home'))


# ── Page Views ──────────────────────────────────────────────────────────────────

def home_view(request):
    programmes = Programme.objects.select_related('school').all().order_by('code')
    return render(request, 'scheduler/home.html', {'programmes': programmes})


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return _redirect_by_role(user)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'scheduler/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('home')
    # Build per-school detail data (used by the Schools section)
    schools_detail = []
    for school in School.objects.all().order_by('name'):
        programmes = list(Programme.objects.filter(school=school).order_by('code'))
        prog_ids = [p.id for p in programmes]

        student_counts = list(
            StudentCount.objects.filter(programme__in=prog_ids)
            .select_related('programme')
            .order_by('programme__code', 'study_year')
        )
        courses = list(
            Course.objects.filter(programme__in=prog_ids)
            .select_related('programme', 'lecturer')
            .order_by('programme__code', 'study_year', 'semester')
        )
        # Unique lecturers for this school (those teaching at least one course)
        lecturer_ids = set(c.lecturer_id for c in courses if c.lecturer_id)
        lecturers = list(Lecturer.objects.filter(id__in=lecturer_ids).order_by('name'))
        # Timetable entries for this school
        timetable = list(
            TimetableEntry.objects.filter(programme__in=prog_ids)
            .select_related('course', 'room', 'timeslot', 'lecturer', 'programme')
            .order_by('programme__code', 'timeslot__day', 'timeslot__start_time')
        )
        schools_detail.append({
            'school': school,
            'programmes': programmes,
            'student_counts': student_counts,
            'courses': courses,
            'lecturers': lecturers,
            'timetable': timetable,
        })

    context = {
        'schools': School.objects.count(),
        'programmes': Programme.objects.count(),
        'courses': Course.objects.count(),
        'lecturers': Lecturer.objects.count(),
        'rooms': Room.objects.count(),
        'timeslots': Timeslot.objects.count(),
        'timetable_entries': TimetableEntry.objects.count(),
        'all_programmes': Programme.objects.select_related('school').all(),
        'all_users': User.objects.select_related('stakeholder').all(),
        'audit_logs': AuditLog.objects.select_related('user').all()[:50],
        # Uploaded data viewer
        'all_rooms': Room.objects.all().order_by('name'),
        'all_lecturers': Lecturer.objects.all().order_by('name'),
        'all_courses': Course.objects.select_related('programme', 'lecturer').order_by(
            'programme__code', 'study_year', 'semester'
        ),
        'all_student_counts': StudentCount.objects.select_related('programme').order_by(
            'programme__code', 'study_year'
        ),
        # Schools detail
        'schools_detail': schools_detail,
    }
    return render(request, 'scheduler/admin.html', context)


@login_required
def coordinator_view(request):
    role = _get_user_role(request.user)
    if role not in ('admin', 'TTC', 'HOD'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    # Build per-school detail (Schools section)
    schools_detail = []
    for school in School.objects.all().order_by('name'):
        programmes = list(Programme.objects.filter(school=school).order_by('code'))
        prog_ids = [p.id for p in programmes]
        student_counts = list(
            StudentCount.objects.filter(programme__in=prog_ids)
            .select_related('programme').order_by('programme__code', 'study_year')
        )
        courses = list(
            Course.objects.filter(programme__in=prog_ids)
            .select_related('programme', 'lecturer')
            .order_by('programme__code', 'study_year', 'semester')
        )
        lecturer_ids = set(c.lecturer_id for c in courses if c.lecturer_id)
        lecturers = list(Lecturer.objects.filter(id__in=lecturer_ids).order_by('name'))
        timetable = list(
            TimetableEntry.objects.filter(programme__in=prog_ids)
            .select_related('course', 'room', 'timeslot', 'lecturer', 'programme')
            .order_by('programme__code', 'timeslot__day', 'timeslot__start_time')
        )
        school_total_students = sum(sc.total_count for sc in student_counts)
        schools_detail.append({
            'school': school,
            'programmes': programmes,
            'student_counts': student_counts,
            'total_students': school_total_students,
            'courses': courses,
            'lecturers': lecturers,
            'timetable': timetable,
        })

    from django.db.models import Sum
    university_total_students = sum(sd['total_students'] for sd in schools_detail)
    total_room_capacity = Room.objects.aggregate(total=Sum('capacity'))['total'] or 0

    context = {
        'programmes': Programme.objects.select_related('school').all().order_by('code'),
        'lecturers': Lecturer.objects.all().order_by('name'),
        'courses': Course.objects.select_related('programme', 'lecturer').order_by(
            'programme__code', 'study_year', 'semester'
        ),
        'schools_detail': schools_detail,
        'university_total_students': university_total_students,
        'total_room_capacity': total_room_capacity,
    }
    return render(request, 'scheduler/coordinator.html', context)


@login_required
def lecturer_view(request):
    user = request.user
    try:
        lecturer = Lecturer.objects.get(email=user.email)
    except Lecturer.DoesNotExist:
        lecturer = None

    entries = []
    total_hours = 0
    if lecturer:
        entries = list(
            TimetableEntry.objects.filter(lecturer=lecturer)
            .select_related('course', 'room', 'timeslot', 'programme')
            .order_by('timeslot__day', 'timeslot__start_time')
        )
        total_hours = sum(e.timeslot.duration_hours for e in entries)

    context = {
        'lecturer': lecturer,
        'entries': entries,
        'total_hours': total_hours,
    }
    return render(request, 'scheduler/lecturer.html', context)


def student_view(request):
    """Public view — no login required."""
    programmes = Programme.objects.select_related('school').all().order_by('code')
    context = {'programmes': programmes}

    prog_id = request.GET.get('programme')
    year = request.GET.get('year')
    semester = request.GET.get('semester')

    if prog_id and year and semester:
        entries = TimetableEntry.objects.filter(
            programme_id=prog_id,
            course__study_year=year,
            course__semester=semester,
            is_exam=False,
        ).select_related('course', 'room', 'timeslot', 'programme', 'lecturer').order_by(
            'timeslot__day', 'timeslot__start_time'
        )
        context['entries'] = entries
        context['selected_programme'] = prog_id
        context['selected_year'] = year
        context['selected_semester'] = semester

    return render(request, 'scheduler/student.html', context)


@login_required
def exam_officer_view(request):
    role = _get_user_role(request.user)
    if role not in ('admin', 'EXAM'):
        messages.error(request, 'Access denied.')
        return redirect('home')
    context = {
        'programmes': Programme.objects.select_related('school').all(),
        'rooms': Room.objects.all(),
        'exam_entries': TimetableEntry.objects.filter(is_exam=True)
            .select_related('course', 'room', 'timeslot', 'programme', 'lecturer')
            .order_by('timeslot__day', 'timeslot__start_time'),
    }
    return render(request, 'scheduler/examination_officer.html', context)


@login_required
def stakeholder_view(request):
    context = {
        'programmes': Programme.objects.select_related('school').all(),
        'total_entries': TimetableEntry.objects.count(),
        'schools': School.objects.prefetch_related('programmes').all(),
    }
    return render(request, 'scheduler/stakeholder.html', context)


# ── Timetable API ────────────────────────────────────────────────────────────────

class GenerateTimetableView(APIView):
    permission_classes = [IsExamOfficerOrCoordinatorOrAdmin]

    def post(self, request):
        programme_ids = request.data.get('programme_ids')
        semester = request.data.get('semester')
        study_years = request.data.get('study_years')
        exam_only = request.data.get('exam_only', False)

        scheduler = HGCSAScheduler()
        try:
            entries, conflicts, unplaced = scheduler.run(
                programme_ids=programme_ids,
                semester=int(semester) if semester else None,
                study_years=[int(y) for y in study_years] if study_years else None,
                exam_only=bool(exam_only),
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        unplaced_codes = [c.code for c in unplaced] if unplaced else []

        log_action(
            request.user, 'GENERATE_TIMETABLE', 'TimetableEntry',
            details=(
                f"Generated {len(entries)} entries, {len(conflicts)} conflicts, "
                f"{len(unplaced_codes)} unplaced: {unplaced_codes}"
            )
        )

        if not conflicts and not unplaced:
            lecturer_emails = list(
                Lecturer.objects.filter(
                    timetable_entries__in=entries
                ).values_list('email', flat=True).distinct()
            )
            prog_code = 'All' if not programme_ids else str(programme_ids)
            notify_timetable_generated(prog_code, semester or 'All', study_years or 'All', lecturer_emails)

        return Response({
            'success': True,
            'entries_count': len(entries),
            'conflicts': conflicts,
            'is_conflict_free': len(conflicts) == 0,
            'unplaced_count': len(unplaced_codes),
            'unplaced_courses': unplaced_codes,
        })


class GenerateAdvancedTimetableView(GenerateTimetableView):
    pass


class CheckConflictsView(APIView):
    permission_classes = [IsExamOfficerOrCoordinatorOrAdmin]

    def get(self, request):
        programme_ids = request.query_params.getlist('programme_ids')
        semester = request.query_params.get('semester')
        exam_only_raw = request.query_params.get('exam_only')

        result = check_all_conflicts(
            programme_ids=[int(p) for p in programme_ids] if programme_ids else None,
            semester=int(semester) if semester else None,
            exam_only=bool(int(exam_only_raw)) if exam_only_raw else None,
        )
        log_action(request.user, 'CHECK_CONFLICTS', 'TimetableEntry', details=str(result['total_conflicts']))
        return Response(result)


class EditTimetableEntryView(APIView):
    permission_classes = [IsExamOfficerOrCoordinatorOrAdmin]

    def post(self, request):
        entry_id = request.data.get('entry_id')
        room_id = request.data.get('room_id')
        timeslot_id = request.data.get('timeslot_id')
        lecturer_id = request.data.get('lecturer_id')

        entry = get_object_or_404(TimetableEntry, id=entry_id)
        old_slot = str(entry.timeslot)

        if room_id:
            entry.room_id = room_id
        if timeslot_id:
            entry.timeslot_id = timeslot_id
        if lecturer_id:
            entry.lecturer_id = lecturer_id

        try:
            entry.save()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        new_slot = str(entry.timeslot)
        log_action(request.user, 'EDIT_ENTRY', 'TimetableEntry', entry.id,
                   f"Changed from {old_slot} to {new_slot}")
        notify_schedule_changed(entry.course.code, old_slot, new_slot,
                                get_lecturer_emails_for_entry(entry))
        return Response(TimetableEntrySerializer(entry).data)


class RescheduleTimetableEntryView(APIView):
    permission_classes = [IsExamOfficerOrCoordinatorOrAdmin]

    def post(self, request):
        entry_id = request.data.get('entry_id')
        timeslot_id = request.data.get('timeslot_id')
        room_id = request.data.get('room_id')

        entry = get_object_or_404(TimetableEntry, id=entry_id)
        old_slot = str(entry.timeslot)
        entry.timeslot_id = timeslot_id
        if room_id:
            entry.room_id = room_id

        try:
            entry.save()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        new_slot = str(entry.timeslot)
        log_action(request.user, 'RESCHEDULE_ENTRY', 'TimetableEntry', entry.id,
                   f"{old_slot} → {new_slot}")
        notify_schedule_changed(entry.course.code, old_slot, new_slot,
                                get_lecturer_emails_for_entry(entry))
        return Response({'success': True, 'entry': TimetableEntrySerializer(entry).data})


class DeleteTimetableEntryView(APIView):
    permission_classes = [IsExamOfficerOrCoordinatorOrAdmin]

    def delete(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        slot_str = str(entry.timeslot)
        course_code = entry.course.code
        emails = get_lecturer_emails_for_entry(entry)
        entry.delete()
        log_action(request.user, 'DELETE_ENTRY', 'TimetableEntry', pk)
        notify_entry_deleted(course_code, slot_str, emails)
        return Response({'success': True})


class DownloadTimetableView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        export_format = request.query_params.get('format', 'excel')
        export_type = request.query_params.get('type', 'by_programme')
        programme_ids = request.query_params.getlist('programme_ids')
        semester = request.query_params.get('semester')
        year = request.query_params.get('year')
        exam_only_raw = request.query_params.get('exam_only', '0')

        qs = TimetableEntry.objects.select_related(
            'course', 'room', 'timeslot', 'programme', 'lecturer'
        )
        if programme_ids:
            qs = qs.filter(programme_id__in=[int(p) for p in programme_ids])
        if semester:
            qs = qs.filter(course__semester=int(semester))
        if year:
            qs = qs.filter(course__study_year=int(year))
        qs = qs.filter(is_exam=bool(int(exam_only_raw)))

        entries = list(qs)

        if export_format == 'pdf':
            file_obj = export_pdf(entries, export_type=export_type)
            response = HttpResponse(file_obj, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="timetable_{export_type}.pdf"'
        else:
            file_obj = export_excel(entries, export_type=export_type)
            response = HttpResponse(
                file_obj,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="timetable_{export_type}.xlsx"'

        return response


# ── Upload API ───────────────────────────────────────────────────────────────────

class UploadRoomsView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        result = parse_rooms(file)
        log_action(request.user, 'UPLOAD_ROOMS', 'Room',
                   details=f"{result['success_count']} rooms, {len(result['errors'])} errors")
        return Response(result)


class UploadCurriculumView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        result = parse_curriculum(file)
        log_action(request.user, 'UPLOAD_CURRICULUM', 'Course',
                   details=f"{result['success_count']} courses")
        return Response(result)


class UploadSchoolsDataView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        result = parse_student_populations(file)
        log_action(request.user, 'UPLOAD_STUDENT_POPULATIONS', 'StudentCount',
                   details=f"{result['success_count']} records")
        return Response(result)


class UploadLecturersView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        result = parse_lecturers(file)
        log_action(request.user, 'UPLOAD_LECTURERS', 'Lecturer',
                   details=f"{result['success_count']} created, {result.get('linked_count', 0)} courses linked")
        return Response(result)


class UploadCourseAssignmentsView(APIView):
    permission_classes = [IsCoordinatorOrAdmin]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        result = parse_course_assignments(file)
        log_action(request.user, 'UPLOAD_COURSE_ASSIGNMENTS', 'Course',
                   details=f"{result['success_count']} assignments")
        return Response(result)


class SeedTimeslotsView(APIView):
    """
    POST /api/admin/seed-timeslots/
    Clears all existing timeslots and creates the official ARDHI schedule:
      07:00-09:00, 09:10-11:10, 11:20-13:20, 13:30-15:30, 15:40-17:40, 17:50-19:50
    Friday 11:20-13:20 is free (not created).
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from datetime import time as t
        from .models import Timeslot

        SLOT_TIMES = [
            (t(7,  0),  t(9,  0)),
            (t(9, 10),  t(11, 10)),
            (t(11, 20), t(13, 20)),   # Friday: skipped
            (t(13, 30), t(15, 30)),
            (t(15, 40), t(17, 40)),
            (t(17, 50), t(19, 50)),
        ]
        FRIDAY_BLOCKED = {(t(11, 20), t(13, 20))}
        DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']

        reset = request.data.get('reset', True)
        deleted = 0
        if reset:
            deleted, _ = Timeslot.objects.all().delete()

        created = 0
        for day in DAYS:
            for start, end in SLOT_TIMES:
                if day == 'FRI' and (start, end) in FRIDAY_BLOCKED:
                    continue
                _, was_created = Timeslot.objects.get_or_create(
                    day=day, start_time=start, end_time=end
                )
                if was_created:
                    created += 1

        log_action(request.user, 'SEED_TIMESLOTS', 'Timeslot',
                   details=f'deleted={deleted}, created={created}')
        return Response({
            'deleted': deleted,
            'created': created,
            'message': (
                f'Timeslots reset. {created} timeslots created '
                f'(Mon–Thu: 6 slots each, Fri: 5 slots — 11:20–13:20 free).'
            )
        })


# ── CRUD ViewSets ─────────────────────────────────────────────────────────────────

class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAdminUser]


class ProgrammeViewSet(viewsets.ModelViewSet):
    queryset = Programme.objects.select_related('school').all()
    serializer_class = ProgrammeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [AllowAny()]


class LecturerViewSet(viewsets.ModelViewSet):
    queryset = Lecturer.objects.all()
    serializer_class = LecturerSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsStakeholderOrAbove()]


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [AllowAny()]


class TimeslotViewSet(viewsets.ModelViewSet):
    queryset = Timeslot.objects.all()
    serializer_class = TimeslotSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [AllowAny()]


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related('programme', 'lecturer').all()
    serializer_class = CourseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for param, field in [('programme', 'programme_id'), ('semester', 'semester'),
                              ('year', 'study_year')]:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [AllowAny()]


class StudentCountViewSet(viewsets.ModelViewSet):
    queryset = StudentCount.objects.select_related('programme').all()
    serializer_class = StudentCountSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [AllowAny()]


class TimetableEntryViewSet(viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.select_related(
        'course', 'room', 'timeslot', 'programme', 'lecturer'
    ).all()
    serializer_class = TimetableEntrySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsExamOfficerOrCoordinatorOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        for param, field in [('programme', 'programme_id'), ('semester', 'course__semester'),
                              ('year', 'course__study_year')]:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{field: val})
        school = self.request.query_params.get('school')
        if school:
            qs = qs.filter(programme__school_id=school)
        exam_only = self.request.query_params.get('exam_only')
        if exam_only is not None:
            qs = qs.filter(is_exam=bool(int(exam_only)))
        return qs

    def perform_create(self, serializer):
        entry = serializer.save()
        log_action(self.request.user, 'CREATE_ENTRY', 'TimetableEntry', entry.id)

    def perform_update(self, serializer):
        entry = serializer.save()
        log_action(self.request.user, 'UPDATE_ENTRY', 'TimetableEntry', entry.id)

    def perform_destroy(self, instance):
        log_action(self.request.user, 'DELETE_ENTRY', 'TimetableEntry', instance.id)
        instance.delete()


# ── Admin User Management ─────────────────────────────────────────────────────────

class ListUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = User.objects.select_related('stakeholder').all()
        return Response(UserSerializer(users, many=True).data)


class RegisterUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        user = User.objects.create_user(
            username=d['username'],
            email=d['email'],
            password=d['password'],
            first_name=d.get('first_name', ''),
            last_name=d.get('last_name', ''),
        )
        role = d['role']
        if role != 'LECTURER':
            Stakeholder.objects.create(user=user, role=role)
        Token.objects.get_or_create(user=user)

        log_action(request.user, 'CREATE_USER', 'User', user.id,
                   f"Created '{user.username}' role='{role}'")
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UpdateUserView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        for field in ('email', 'first_name', 'last_name'):
            val = request.data.get(field)
            if val is not None:
                setattr(user, field, val)
        is_active = request.data.get('is_active')
        if is_active is not None:
            user.is_active = bool(is_active)
        user.save()

        role = request.data.get('role')
        if role:
            Stakeholder.objects.update_or_create(user=user, defaults={'role': role})

        log_action(request.user, 'UPDATE_USER', 'User', user.id, f"Updated '{user.username}'")
        return Response(UserSerializer(user).data)


class DeleteUserView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            return Response({'error': 'Cannot delete your own account.'},
                            status=status.HTTP_400_BAD_REQUEST)
        username = user.username
        user.delete()
        log_action(request.user, 'DELETE_USER', 'User', pk, f"Deleted '{username}'")
        return Response({'success': True})


# ── Bulk Clear Views (Uploaded Data) ─────────────────────────────────────────────

class ClearDataView(APIView):
    """Generic bulk-delete view. Subclasses set `model` and `label`."""
    permission_classes = [IsAdminUser]
    model = None
    label = 'records'

    def delete(self, request):
        count, _ = self.model.objects.all().delete()
        log_action(request.user, f'CLEAR_{self.label.upper()}', self.label, details=f"Deleted {count} records")
        return Response({'deleted': count})


class ClearRoomsView(ClearDataView):
    model = Room
    label = 'rooms'


class ClearLecturersView(ClearDataView):
    model = Lecturer
    label = 'lecturers'


class ClearCoursesView(ClearDataView):
    model = Course
    label = 'courses'


class ClearProgrammesView(ClearDataView):
    model = Programme
    label = 'programmes'


class ClearStudentCountsView(ClearDataView):
    model = StudentCount
    label = 'studentcounts'


class ClearTimetableView(APIView):
    """
    DELETE /api/timetable/clear/
    Deletes all TimetableEntry records (full reset).
    Optionally filter by programme_ids or school_id via query params.
    Accessible by admin or coordinator (TTC/HOD).
    """
    permission_classes = [IsCoordinatorOrAdmin]

    def delete(self, request):
        programme_ids = request.query_params.getlist('programme')
        school_id = request.query_params.get('school')

        qs = TimetableEntry.objects.all()
        if programme_ids:
            qs = qs.filter(programme__id__in=programme_ids)
        elif school_id:
            qs = qs.filter(programme__school__id=school_id)

        count, _ = qs.delete()
        log_action(request.user, 'CLEAR_TIMETABLE', 'TimetableEntry',
                   details=f"Deleted {count} entries")
        return Response({'deleted': count, 'message': f'{count} timetable entries deleted.'})


# ── DRF Token Auth ────────────────────────────────────────────────────────────────

class ObtainTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'role': _get_user_role(user),
        })
