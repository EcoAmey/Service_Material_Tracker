from django.apps import AppConfig


class TrackerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracker'

    def ready(self):
        # The users table has no last_login column, so Django's built-in
        # "record last login time" signal would fail on every login.
        from django.contrib.auth.models import update_last_login
        from django.contrib.auth.signals import user_logged_in

        user_logged_in.disconnect(update_last_login)
