from django import template

register = template.Library()


@register.filter
def get_role_display(user):
    """Return the display name of a user's role."""
    if user.is_superuser:
        return 'Admin'
    try:
        return user.stakeholder.get_role_display()
    except Exception:
        return 'User'


@register.filter
def time_range(timeslot):
    """Format timeslot as HH:MM–HH:MM."""
    try:
        return f"{timeslot.start_time.strftime('%H:%M')}–{timeslot.end_time.strftime('%H:%M')}"
    except Exception:
        return str(timeslot)


@register.filter
def duration_hours(timeslot):
    """Return duration in hours as string."""
    try:
        return f"{timeslot.duration_hours:.1f}h"
    except Exception:
        return ''


@register.filter
def day_abbr(timeslot):
    """Return abbreviated day name."""
    try:
        return timeslot.get_day_display()[:3]
    except Exception:
        return ''


@register.filter
def is_coordinator_or_admin(user):
    if user.is_superuser:
        return True
    try:
        return user.stakeholder.role in ('TTC', 'HOD')
    except Exception:
        return False


@register.filter
def is_exam_officer(user):
    try:
        return user.stakeholder.role == 'EXAM'
    except Exception:
        return False


@register.filter
def lecturer_name_or_tba(entry):
    if entry.lecturer:
        return entry.lecturer.name
    return 'TBA'


@register.simple_tag
def active_if(current_view, target_view):
    """Return 'active' if current view matches target."""
    return 'active' if current_view == target_view else ''
