"""
Audit logging helper.
Call log_action() from every mutating view.
"""
from .models import AuditLog


def log_action(user, action, target_model, target_id='', details=''):
    """
    Create an AuditLog entry.

    Args:
        user: Django User instance (or None for anonymous)
        action: str e.g. 'UPLOAD_ROOMS', 'GENERATE_TIMETABLE', 'DELETE_ENTRY'
        target_model: str e.g. 'Room', 'TimetableEntry'
        target_id: str or int — primary key of affected object
        details: str — human-readable description
    """
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        target_model=target_model,
        target_id=str(target_id),
        details=details,
    )
