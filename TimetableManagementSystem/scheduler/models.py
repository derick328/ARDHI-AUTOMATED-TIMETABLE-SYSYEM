from django.db import models
from django.contrib.auth.models import User


class School(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"


class Programme(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='programmes')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"


class Lecturer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    is_full_time = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField()
    is_lab = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        lab_tag = ' [LAB]' if self.is_lab else ''
        return f"{self.name} (cap:{self.capacity}){lab_tag}"


class Timeslot(models.Model):
    DAY_CHOICES = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
    ]

    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('day', 'start_time', 'end_time')
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.get_day_display()} {self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

    @property
    def duration_hours(self):
        from datetime import datetime, date
        start = datetime.combine(date.today(), self.start_time)
        end = datetime.combine(date.today(), self.end_time)
        return (end - start).seconds / 3600


class Course(models.Model):
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=300)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='courses')
    semester = models.PositiveSmallIntegerField()   # 1 or 2
    study_year = models.PositiveSmallIntegerField()  # 1, 2, 3, or 4
    lecturer = models.ForeignKey(
        Lecturer, null=True, blank=True, on_delete=models.SET_NULL, related_name='courses'
    )
    is_exam = models.BooleanField(default=False)
    is_lab = models.BooleanField(default=False)
    # Shared-venue group: courses with the same non-null value are scheduled
    # into the same room+timeslot (combined student count used for room sizing).
    merge_group = models.CharField(max_length=100, blank=True, null=True, default=None,
                                   help_text='Leave blank for no sharing. '
                                             'Courses with the same value share a room.')

    class Meta:
        ordering = ['programme', 'study_year', 'semester', 'code']
        unique_together = ('code', 'programme')

    def __str__(self):
        return f"{self.code} — {self.title}"


class StudentCount(models.Model):
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='student_counts')
    study_year = models.PositiveSmallIntegerField()
    male_count = models.PositiveIntegerField(default=0)
    female_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('programme', 'study_year')
        ordering = ['programme', 'study_year']

    def __str__(self):
        return f"{self.programme.code} Year {self.study_year}: {self.total_count} students"

    def save(self, *args, **kwargs):
        if not self.total_count:
            self.total_count = self.male_count + self.female_count
        super().save(*args, **kwargs)


class TimetableEntry(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='timetable_entries')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='timetable_entries')
    timeslot = models.ForeignKey(Timeslot, on_delete=models.CASCADE, related_name='timetable_entries')
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='timetable_entries')
    lecturer = models.ForeignKey(
        Lecturer, null=True, blank=True, on_delete=models.SET_NULL, related_name='timetable_entries'
    )
    is_exam = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'timeslot'],
                name='unique_room_timeslot'
            ),
            models.UniqueConstraint(
                fields=['programme', 'timeslot', 'course'],
                name='unique_programme_timeslot_course'
            ),
        ]
        ordering = ['timeslot__day', 'timeslot__start_time', 'programme']

    def __str__(self):
        return f"{self.course.code} | {self.room.name} | {self.timeslot}"


class Stakeholder(models.Model):
    ROLE_CHOICES = [
        ('DUP', 'DUP'),
        ('HOD', 'HOD'),
        ('TTC', 'TTC (Coordinator)'),
        ('DEAN', 'Dean'),
        ('ICTD', 'ICTD'),
        ('EXAM', 'Examination Officer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stakeholder')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} [{self.get_role_display()}]"


class AuditLog(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs'
    )
    action = models.CharField(max_length=100)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} — {self.action} on {self.target_model}"


class UploadedCourseAssignment(models.Model):
    course_code = models.CharField(max_length=20)
    lecturer_name = models.CharField(max_length=200)
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='success')
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-upload_timestamp']

    def __str__(self):
        return f"{self.course_code} → {self.lecturer_name} [{self.status}]"
