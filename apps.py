import importlib

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field: str = "django.db.models.AutoField"
    # This app is installed into apps/<folder>/ so the module path is apps.<folder>.
    # Using __package__ keeps it portable when installed with any folder name.
    name = __package__

    def ready(self):
        # Ensure signals are loaded
        importlib.import_module(f"{__package__}.signals")
