from django.contrib import admin
from .models import (
    School, Programme, Lecturer, Room, Timeslot,
    Course, StudentCount, TimetableEntry,
    Stakeholder, AuditLog, UploadedCourseAssignment
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('name', 'code')


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'school')
    list_filter = ('school',)
    search_fields = ('name', 'code')


@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_full_time')
    list_filter = ('is_full_time',)
    search_fields = ('name', 'email')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'is_lab')
    list_filter = ('is_lab',)
    search_fields = ('name',)


@admin.register(Timeslot)
class TimeslotAdmin(admin.ModelAdmin):
    list_display = ('day', 'start_time', 'end_time')
    list_filter = ('day',)
    ordering = ('day', 'start_time')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'programme', 'study_year', 'semester', 'lecturer', 'is_exam', 'is_lab')
    list_filter = ('programme__school', 'semester', 'study_year', 'is_exam', 'is_lab')
    search_fields = ('code', 'title', 'lecturer__name')


@admin.register(StudentCount)
class StudentCountAdmin(admin.ModelAdmin):
    list_display = ('programme', 'study_year', 'male_count', 'female_count', 'total_count')
    list_filter = ('study_year',)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('course', 'room', 'timeslot', 'programme', 'lecturer', 'is_exam')
    list_filter = ('is_exam', 'timeslot__day', 'programme')
    search_fields = ('course__code', 'course__title', 'room__name', 'lecturer__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Stakeholder)
class StakeholderAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'target_model', 'target_id')
    list_filter = ('action', 'target_model')
    search_fields = ('user__username', 'action', 'details')
    readonly_fields = ('timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UploadedCourseAssignment)
class UploadedCourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'lecturer_name', 'upload_timestamp', 'status')
    list_filter = ('status',)
    readonly_fields = ('upload_timestamp',)
