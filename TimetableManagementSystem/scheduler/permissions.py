"""
Custom DRF permission classes for role-based access control.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminUser(BasePermission):
    """Only Django superusers."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsCoordinatorOrAdmin(BasePermission):
    """Superuser OR Stakeholder with role TTC or HOD."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.stakeholder.role in ('TTC', 'HOD')
        except Exception:
            return False


class IsExamOfficer(BasePermission):
    """Superuser OR Stakeholder with role EXAM."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.stakeholder.role == 'EXAM'
        except Exception:
            return False


class IsExamOfficerOrCoordinatorOrAdmin(BasePermission):
    """Can generate/edit timetables: Admin, Coordinator, or Exam Officer."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.stakeholder.role in ('TTC', 'HOD', 'EXAM')
        except Exception:
            return False


class IsStakeholderOrAbove(BasePermission):
    """Any authenticated user (all roles)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsLecturerOrAbove(BasePermission):
    """Lecturers can read-only; higher roles can do more."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsPublicOrAuthenticated(BasePermission):
    """Safe (GET) methods are public; mutations require auth."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)
