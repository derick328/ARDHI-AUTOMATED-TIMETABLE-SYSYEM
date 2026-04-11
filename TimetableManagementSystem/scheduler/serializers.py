from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    School, Programme, Lecturer, Room, Timeslot,
    Course, StudentCount, TimetableEntry,
    Stakeholder, AuditLog, UploadedCourseAssignment
)


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = '__all__'


class ProgrammeSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Programme
        fields = ['id', 'name', 'code', 'school', 'school_name']


class LecturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lecturer
        fields = '__all__'


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'


class TimeslotSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = Timeslot
        fields = ['id', 'day', 'start_time', 'end_time', 'display']

    def get_display(self, obj):
        return str(obj)


class CourseSerializer(serializers.ModelSerializer):
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    lecturer_name = serializers.CharField(source='lecturer.name', read_only=True, allow_null=True)

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'programme', 'programme_name',
            'semester', 'study_year', 'lecturer', 'lecturer_name',
            'is_exam', 'is_lab'
        ]


class StudentCountSerializer(serializers.ModelSerializer):
    programme_code = serializers.CharField(source='programme.code', read_only=True)

    class Meta:
        model = StudentCount
        fields = ['id', 'programme', 'programme_code', 'study_year',
                  'male_count', 'female_count', 'total_count']


class TimetableEntrySerializer(serializers.ModelSerializer):
    # Nested read-only fields for display
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_study_year = serializers.IntegerField(source='course.study_year', read_only=True)
    course_semester = serializers.IntegerField(source='course.semester', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    room_capacity = serializers.IntegerField(source='room.capacity', read_only=True)
    timeslot_display = serializers.CharField(source='timeslot.__str__', read_only=True)
    timeslot_day = serializers.CharField(source='timeslot.day', read_only=True)
    timeslot_day_display = serializers.CharField(source='timeslot.get_day_display', read_only=True)
    timeslot_start = serializers.TimeField(source='timeslot.start_time', read_only=True)
    timeslot_end = serializers.TimeField(source='timeslot.end_time', read_only=True)
    programme_code = serializers.CharField(source='programme.code', read_only=True)
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    lecturer_name = serializers.CharField(source='lecturer.name', read_only=True, allow_null=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'course', 'course_code', 'course_title', 'course_study_year', 'course_semester',
            'room', 'room_name', 'room_capacity',
            'timeslot', 'timeslot_display', 'timeslot_day', 'timeslot_day_display',
            'timeslot_start', 'timeslot_end',
            'programme', 'programme_code', 'programme_name',
            'lecturer', 'lecturer_name',
            'is_exam', 'created_at', 'updated_at'
        ]


class StakeholderSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Stakeholder
        fields = ['id', 'user', 'username', 'email', 'role']


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'username', 'action', 'target_model',
                  'target_id', 'timestamp', 'details']


class UploadedCourseAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedCourseAssignment
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'is_superuser', 'is_active', 'role']

    def get_role(self, obj):
        try:
            return obj.stakeholder.get_role_display()
        except Exception:
            if obj.is_superuser:
                return 'Admin'
            return 'N/A'


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    role = serializers.ChoiceField(choices=[
        ('TTC', 'Coordinator'), ('HOD', 'HOD'), ('EXAM', 'Exam Officer'),
        ('DUP', 'DUP'), ('DEAN', 'Dean'), ('ICTD', 'ICTD'), ('LECTURER', 'Lecturer')
    ])

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value
