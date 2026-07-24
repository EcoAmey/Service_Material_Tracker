from django.contrib.auth.backends import BaseBackend

from .models import User


class RoleBackend(BaseBackend):
    """Authenticates users of one specific role against the users table.
    Subclass and set `role` to restrict a login form to that role."""

    role = None

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            user = User.objects.get(
                email__iexact=username, role=self.role, status='active'
            )
        except User.DoesNotExist:
            return None
        return user if user.check_password(password) else None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class EngineerBackend(RoleBackend):
    role = 'engineer'


class RegionalWarehouseBackend(RoleBackend):
    role = 'regwarehouse'


class WarehouseBackend(RoleBackend):
    role = 'warehouse'


class ServiceDeskBackend(RoleBackend):
    role = 'servicedesk'


class ElectronicsBackend(RoleBackend):
    role = 'electronics'
