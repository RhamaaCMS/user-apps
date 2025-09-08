# apps/users/settings.py

# Extend INSTALLED_APPS with allauth + allauth-ui
INSTALLED_APPS = [
    # allauth-ui should precede allauth so its templates override
    "allauth_ui",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "widget_tweaks",
]

# Authentication backends (keep Django default + allauth)
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django.contrib.sites
SITE_ID = 1

# Core allauth configuration (adjust as needed)
# New style settings (v0.63+)
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "username*",
    "password1*",
    "password2*",
]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  # or "mandatory" / "none"

# Legacy settings (pre-0.63) for backward compatibility
# If you are on allauth < 0.63, these will be used.
ACCOUNT_AUTHENTICATION_METHOD = "username_email"  # or "email" / "username"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True

# Redirects
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Optional: custom user model if/when you switch
# AUTH_USER_MODEL = "users.User"

# Optional: providers
# SOCIALACCOUNT_PROVIDERS = {
#     "google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}},
# }


# Register middleware to expose /accounts/ at root via redirect to /users/accounts/
MIDDLEWARE = [
    # Allauth middleware requirement (v0.63+)
    "allauth.account.middleware.AccountMiddleware",
]
