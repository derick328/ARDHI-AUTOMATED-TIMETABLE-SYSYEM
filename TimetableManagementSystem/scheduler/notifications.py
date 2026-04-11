"""
Email notification helpers.
Uses Django's built-in mail framework.
In development the console backend prints emails to stdout.
"""
from django.core.mail import send_mail
from django.conf import settings


def notify_timetable_generated(programme_code, semester, year, recipient_emails):
    """Send notification when a timetable is generated."""
    if not recipient_emails:
        return
    send_mail(
        subject=f'[ARDHI Timetable] Timetable Generated — {programme_code} Sem {semester} Year {year}',
        message=(
            f'Dear Recipient,\n\n'
            f'The timetable for {programme_code} (Semester {semester}, Year {year}) '
            f'has been successfully generated and is now available for viewing.\n\n'
            f'Please log in to the ARDHI Timetable System to view and download your schedule.\n\n'
            f'ARDHI University Timetable System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=True,
    )


def notify_schedule_changed(course_code, old_slot, new_slot, recipient_emails):
    """Send notification when a timetable entry is rescheduled."""
    if not recipient_emails:
        return
    send_mail(
        subject=f'[ARDHI Timetable] Schedule Change — {course_code}',
        message=(
            f'Dear Recipient,\n\n'
            f'Course {course_code} has been rescheduled.\n\n'
            f'Previous time: {old_slot}\n'
            f'New time: {new_slot}\n\n'
            f'Please log in to the ARDHI Timetable System for full details.\n\n'
            f'ARDHI University Timetable System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=True,
    )


def notify_entry_deleted(course_code, slot, recipient_emails):
    """Send notification when a timetable entry is deleted."""
    if not recipient_emails:
        return
    send_mail(
        subject=f'[ARDHI Timetable] Entry Removed — {course_code}',
        message=(
            f'Dear Recipient,\n\n'
            f'The timetable entry for course {course_code} ({slot}) has been removed.\n\n'
            f'Please contact your coordinator if this was unexpected.\n\n'
            f'ARDHI University Timetable System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=True,
    )


def get_lecturer_emails_for_entry(entry):
    """Return list of emails to notify for a given TimetableEntry."""
    emails = []
    if entry.lecturer and entry.lecturer.email:
        emails.append(entry.lecturer.email)
    return emails
