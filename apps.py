import importlib

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field: str = "django.db.models.AutoField"
    # Installed as apps/<folder>/; module is apps.<folder> (e.g. apps.users)
    name = __package__

    def ready(self):
        importlib.import_module(f"{__package__}.signals")

        # Dynamically inject allauth URLs at the project root to expose
        # un-namespaced URL names like 'account_signup' expected by allauth.
        try:
            from django.conf import settings
            from django.urls import include, path
            from importlib import import_module

            root_urls = import_module(settings.ROOT_URLCONF)

            # Avoid duplicating if already added
            already_added = any(
                getattr(p, "name", None) == "account_login" or
                (getattr(p, "url_patterns", None) and any(getattr(pp, "name", None) == "account_login" for pp in getattr(p, "url_patterns", [])))
                for p in getattr(root_urls, "urlpatterns", [])
            )

            if not already_added:
                root_urls.urlpatterns.insert(0, path("accounts/", include("allauth.urls")))
        except Exception:
            # Fail silently if URL injection is not possible at this stage
            pass