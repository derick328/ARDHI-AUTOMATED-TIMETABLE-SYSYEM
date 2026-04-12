from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views

# DRF Router for CRUD ViewSets
router = DefaultRouter()
router.register(r'schools', views.SchoolViewSet, basename='school')
router.register(r'programmes', views.ProgrammeViewSet, basename='programme')
router.register(r'lecturers', views.LecturerViewSet, basename='lecturer')
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'timeslots', views.TimeslotViewSet, basename='timeslot')
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'student-counts', views.StudentCountViewSet, basename='studentcount')
router.register(r'timetable-entries', views.TimetableEntryViewSet, basename='timetableentry')

urlpatterns = [
    # ── Page routes ──────────────────────────────────────────────────────────────
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('coordinator/', views.coordinator_view, name='coordinator'),
    path('lecturer/', views.lecturer_view, name='lecturer'),
    path('student/', views.student_view, name='student'),
    path('examination-officer/', views.exam_officer_view, name='exam_officer'),
    path('stakeholder/', views.stakeholder_view, name='stakeholder'),

    # ── Timetable API ─────────────────────────────────────────────────────────────
    path('api/timetable/generate/', views.GenerateTimetableView.as_view(), name='generate_timetable'),
    path('api/timetable/generate-advanced/', views.GenerateAdvancedTimetableView.as_view(), name='generate_advanced'),
    path('api/timetable/check-conflicts/', views.CheckConflictsView.as_view(), name='check_conflicts'),
    path('api/timetable/edit/', views.EditTimetableEntryView.as_view(), name='edit_entry'),
    path('api/timetable/reschedule/', views.RescheduleTimetableEntryView.as_view(), name='reschedule_entry'),
    path('api/timetable/delete-entry/<int:pk>/', views.DeleteTimetableEntryView.as_view(), name='delete_entry'),
    path('api/download-interactive-timetable/', views.DownloadTimetableView.as_view(), name='download_timetable'),

    # ── Upload API ────────────────────────────────────────────────────────────────
    path('api/upload/rooms/', views.UploadRoomsView.as_view(), name='upload_rooms'),
    path('api/upload/curriculum-only/', views.UploadCurriculumView.as_view(), name='upload_curriculum'),
    path('api/upload/schools-data/', views.UploadSchoolsDataView.as_view(), name='upload_schools'),
    path('api/upload/lecturers/', views.UploadLecturersView.as_view(), name='upload_lecturers'),
    path('api/upload-simple-course-assignments/', views.UploadCourseAssignmentsView.as_view(), name='upload_assignments'),

    # ── CRUD API (ViewSets) ───────────────────────────────────────────────────────
    path('api/', include(router.urls)),

    # ── Timeslot Seeder ───────────────────────────────────────────────────────────
    path('api/admin/seed-timeslots/', views.SeedTimeslotsView.as_view(), name='seed_timeslots'),

    # ── Timetable Clear ───────────────────────────────────────────────────────────
    path('api/timetable/clear/', views.ClearTimetableView.as_view(), name='clear_timetable'),

    # ── Bulk Clear (Uploaded Data) ────────────────────────────────────────────────
    path('api/admin/clear/rooms/', views.ClearRoomsView.as_view(), name='clear_rooms'),
    path('api/admin/clear/lecturers/', views.ClearLecturersView.as_view(), name='clear_lecturers'),
    path('api/admin/clear/courses/', views.ClearCoursesView.as_view(), name='clear_courses'),
    path('api/admin/clear/programmes/', views.ClearProgrammesView.as_view(), name='clear_programmes'),
    path('api/admin/clear/student-counts/', views.ClearStudentCountsView.as_view(), name='clear_student_counts'),

    # ── Admin User Management ─────────────────────────────────────────────────────
    path('api/admin/users/', views.ListUsersView.as_view(), name='list_users'),
    path('api/admin/register-user/', views.RegisterUserView.as_view(), name='register_user'),
    path('api/admin/update-user/<int:pk>/', views.UpdateUserView.as_view(), name='update_user'),
    path('api/admin/delete-user/<int:pk>/', views.DeleteUserView.as_view(), name='delete_user'),

    # ── Token Auth ────────────────────────────────────────────────────────────────
    path('api/token/', views.ObtainTokenView.as_view(), name='obtain_token'),
    path('api/token-auth/', obtain_auth_token, name='api_token_auth'),
]
