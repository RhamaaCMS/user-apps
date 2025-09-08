# Users App

A pluggable Django app (under `apps/users/`) that extends authentication and profile features for the project. It integrates `django-allauth` and `django-allauth-ui`, while keeping configuration self-contained in the app via the project's auto-import pattern.

## Overview

- Exposes full `django-allauth` auth flow using `allauth-ui` for modern UI.
- Keeps settings and URLs localized in `apps/users/` and auto-merged into the global project settings.
- Supports both `/users/accounts/...` (namespaced) and `/accounts/...` (root) routes without editing the project root URLs.
- Provides profile views: `accounts/profile/` (private) and `@<username>/` (public).

## Directory Structure

- `apps/users/settings.py` — App-local settings merged into global settings:
  - Registers `allauth`, `allauth.account`, `allauth.socialaccount`, `allauth_ui`, and `widget_tweaks` in `INSTALLED_APPS`.
  - Configures authentication backends and allauth options (new API plus legacy for compatibility).
  - Adds `allauth.account.middleware.AccountMiddleware` to `MIDDLEWARE`.
- `apps/users/urls.py` — Includes allauth routes under `accounts/` plus user-specific routes.
- `apps/users/apps.py` — AppConfig that loads signals and injects `allauth.urls` at the project root under `/accounts/` so un-namespaced URL names like `account_login` and `account_signup` resolve correctly.
- `apps/users/views.py` — App views (e.g., `profile_view`, `public_profile_view`).
- `apps/users/templates/` — Templates (including overrides for allauth/allauth-ui if any).
- `apps/users/models.py` — Models for user extension (profile or custom user model scaffolding).
- `apps/users/signals.py` — Signals (e.g., social account hooks).

## Requirements

Add these to the project requirements (already added at project level `requirements.txt`):

- `django-allauth`
- `django-allauth-ui`
- `django-widget-tweaks`

If you prefer app-scoped requirements, see `apps/users/requirements.txt`.

## Installation & Setup

1. Ensure the project auto-imports app settings and URLs (already provided in the project):
   - `DevUserApps/DevUserApps/settings/base.py`
     - Auto-discovers apps under `apps/` and merges `apps/<app>/settings.py` into global settings.
   - `DevUserApps/DevUserApps/urls.py`
     - Auto-includes `apps/<app>/urls.py` under `/<app_name>/` with namespace.

2. Dependencies:
   - Install packages (from project root):
     ```bash
     pip install -r requirements.txt
     ```

3. Database & static:
   - Run migrations and collect static:
     ```bash
     python manage.py migrate
     python manage.py collectstatic --noinput
     ```

## Configuration (apps/users/settings.py)

Key settings included and auto-merged:

- `INSTALLED_APPS += ["allauth_ui", "django.contrib.sites", "allauth", "allauth.account", "allauth.socialaccount", "widget_tweaks"]`
- `AUTHENTICATION_BACKENDS` keeps Django default plus `allauth` backend.
- `SITE_ID = 1` (ensure a Site with ID 1 exists — default for new projects).
- New allauth API:
  - `ACCOUNT_LOGIN_METHODS = {"email", "username"}`
  - `ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]`
  - `ACCOUNT_UNIQUE_EMAIL = True`
  - `ACCOUNT_EMAIL_VERIFICATION = "optional"`
- Legacy allauth API (for older versions):
  - `ACCOUNT_AUTHENTICATION_METHOD = "username_email"`
  - `ACCOUNT_EMAIL_REQUIRED = True`
  - `ACCOUNT_USERNAME_REQUIRED = True`
- Middleware:
  - `allauth.account.middleware.AccountMiddleware`

Redirects:
- `LOGIN_REDIRECT_URL = "/"`
- `LOGOUT_REDIRECT_URL = "/"`

## URL Routing

- App URLs are defined in `apps/users/urls.py`:
  ```python
  from django.urls import include, path
  from .views import profile_view, public_profile_view

  app_name = "users"

  urlpatterns = [
      path("accounts/", include("allauth.urls")),
      path("accounts/profile/", profile_view, name="profile"),
      path("@<str:username>/", public_profile_view, name="public_profile"),
  ]
  ```

- Auto-included by the project under `/users/` prefix: e.g., `/users/accounts/login/`.
- Root-level `/accounts/` is also available: `UsersConfig.ready()` injects `path("accounts/", include("allauth.urls"))` into the root URLConf at runtime. This ensures allauth’s un-namespaced reverse lookups (e.g., `account_signup`) work.

## Templates

- The app uses `allauth-ui` defaults. To customize, override its templates under `apps/users/templates/` with the same paths as upstream.
- `widget_tweaks` is available for simple form rendering customization.

## Extending the User Model

Two recommended approaches:

- Profile model (OneToOne with `django.contrib.auth.get_user_model()`):
  - Safest if the project already has auth migrations applied.
- Custom user model (`AbstractUser` or `AbstractBaseUser`):
  - Set `AUTH_USER_MODEL = "users.User"` in `apps/users/settings.py` before initial migrations.
  - Update any ForeignKeys/relations to reference the custom user model.

## Signals

- `apps/users/signals.py` can react to allauth events (e.g., sync social account data).
- Ensure imports happen via `UsersConfig.ready()` (already set).

## Development Notes

- The project’s development settings use `DevUserApps.settings.dev`. Ensure local development runs via this module.
- When debugging URL issues, visit:
  - `/users/accounts/login/` (namespace-mounted)
  - `/accounts/login/` (root, injected at runtime by `UsersConfig.ready()`).
- If you see `NoReverseMatch: 'account_signup'`, confirm that:
  - `apps/users/apps.py` is loading (AppConfig used), and
  - `UsersConfig.ready()` successfully injected root accounts URLs, and
  - `INSTALLED_APPS` contains `allauth` and `allauth.account`.

## Troubleshooting

- Missing middleware error:
  - Add `"allauth.account.middleware.AccountMiddleware"` to `MIDDLEWARE` (already included via `apps/users/settings.py`).

- Static files / collectstatic errors in development:
  - Some third-party packages may reference assets not present locally. If needed, switch to `StaticFilesStorage` during dev to avoid Manifest strictness.

- Sites framework:
  - Ensure `SITE_ID = 1` exists (`django.contrib.sites`). Use Django admin to verify/edit Sites entries.

## License

This app follows the project’s LICENSE.
