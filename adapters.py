"""
Custom django-allauth adapters untuk form signup & social login.

Handles:
- Email validation & uniqueness
- Username auto-generation & validation
- User creation & profile setup
- Login/signup redirects
- Social account connection
- Anti-spam: disposable email blacklist, honeypot validation
"""

import hashlib
import logging
import re
from typing import Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm as AllauthSignupForm
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from hcaptcha.fields import hCaptchaField

User = get_user_model()
logger = logging.getLogger(__name__)

# Blacklist domain email sekali pakai (disposable/temporary emails)
DISPOSABLE_EMAIL_DOMAINS = {
    # Generic disposable
    "tempmail.com", "throwaway.com", "mailinator.com", "guerrillamail.com",
    "sharklasers.com", "spam4.me", "trashmail.com", "yopmail.com",
    "getairmail.com", "temp-mail.org", "fake-email.com", "receiveee.com",
    # Known spam domains dari screenshot
    "jmjfire.com", "firemail.cc", "mailforspam.com", "spamgourmet.com",
    # Temp email services
    "10minutemail.com", "20minute.email", "tempmailaddress.com",
    "burnermail.io", "tempail.com", "throwawaymail.com", "temp-mail.io",
    "mailnesia.com", "tempinbox.com", "disposableemail.org",
    # Other suspicious patterns
    "mail.ru", "yandex.ru", "bk.ru", "list.ru", "inbox.ru", "internet.ru",
    # Additional disposable domains
    "tmpmail.org", "mail-temp.com", "tempemail.com", "tmpbox.net",
    "mailsac.com", "inboxkitten.com", "getnada.com", "tempmailbox.com",
    "zoho.in", "zoho.com.cn", "protonmail.ch", "tutanota.de",
}

# Regex untuk mendeteksi username generated (random string)
RANDOM_USERNAME_PATTERNS = [
    re.compile(r'^[a-z]{8,}$'),  # 8+ lowercase chars (reduced from 10)
    re.compile(r'^[a-z0-9]{8,}$'),  # 8+ alphanumeric lowercase
    re.compile(r'^[b-df-hj-np-tv-z]{6,}$'),  # Consonants only - 6+ chars (reduced from 8)
]

# Additional pattern: repeated character sequences
REPETITIVE_PATTERN = re.compile(r'(.)\1{2,}')  # Same char 3+ times in a row

# Common bot name patterns
BOT_NAME_INDICATORS = [
    'bot', 'spam', 'fake', 'temp', 'test', 'admin', 'root', 'user', 'guest', 'anonymous'
]


def is_disposable_email(email: str) -> bool:
    """Check if email is from disposable email provider."""
    domain = email.split("@")[-1].lower()
    return domain in DISPOSABLE_EMAIL_DOMAINS


def is_suspicious_username(username: str) -> bool:
    """Detect bot-generated random usernames with stricter rules."""
    if not username:
        return True  # Empty username is suspicious
    
    username_lower = username.lower()
    
    # Check against common bot names
    for indicator in BOT_NAME_INDICATORS:
        if indicator in username_lower:
            return True
    
    # Check for repetitive characters (e.g., zzz, abcabcabc)
    if REPETITIVE_PATTERN.search(username_lower):
        return True
    
    # Check for too many repeated chars overall
    char_ratio = len(set(username_lower)) / len(username_lower) if len(username) > 0 else 0
    if len(username) >= 8 and char_ratio < 0.4:  # Less than 40% unique chars
        return True
    
    # Check against random patterns
    for pattern in RANDOM_USERNAME_PATTERNS:
        if pattern.match(username_lower):
            return True
    
    # Check for no vowels (likely generated) - untuk username 6+ karakter
    vowels = set('aeiou')
    if len(username) >= 6 and not any(c in vowels for c in username_lower):
        return True
    
    # Check for alternating pattern (e.g., ababab, xyzyzy)
    if len(username) >= 6:
        # Check if pattern repeats every 2 chars
        if username_lower[0:2] * (len(username)//2) == username_lower[:len(username)//2*2]:
            return True
        # Check if pattern repeats every 3 chars
        if len(username) >= 9:
            if username_lower[0:3] * (len(username)//3) == username_lower[:len(username)//3*3]:
                return True
    
    return False


class SignupFormWithCaptcha(AllauthSignupForm):
    """Extended signup form with hCaptcha and honeypot."""
    
    # Honeypot field - should remain empty
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'style': 'display:none !important;',
            'tabindex': '-1',
            'autocomplete': 'off'
        }),
        label=""
    )
    
    # hCaptcha field
    hcaptcha = hCaptchaField()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make sure hcaptcha is rendered properly
        self.fields['hcaptcha'].widget.attrs.update({
            'data-theme': 'light',
        })
    
    def clean_website(self):
        """Honeypot validation - reject if field is filled."""
        website = self.cleaned_data.get('website', '')
        if website:
            logger.warning(f"Honeypot triggered - bot signup attempt blocked")
            raise ValidationError("Spam detected.")
        return website
    
    def clean_hcaptcha(self):
        """Validate hCaptcha response."""
        hcaptcha_response = self.cleaned_data.get('hcaptcha')
        if not hcaptcha_response:
            raise ValidationError("Please complete the CAPTCHA.")
        return hcaptcha_response



class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter untuk form-based signup & login.

    Fitur:
    - Email validation (unique, format, disposable domain check)
    - Username auto-generation dari email + bot detection
    - Anti-spam: disposable email blacklist, honeypot
    - Auto-create UserProfile setelah signup
    - Custom redirect setelah login/signup
    """
    
    def get_signup_form_class(self):
        """Return extended signup form with CAPTCHA."""
        return SignupFormWithCaptcha

    def clean_email(self, email):
        """
        Validasi email: unique, format valid, lowercase, not disposable.

        Args:
            email (str): Email address to validate

        Returns:
            str: Cleaned email (lowercase, stripped)

        Raises:
            ValidationError: Jika email sudah terdaftar, invalid, atau disposable
        """
        email = email.lower().strip()

        # Cek email sudah terdaftar
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email sudah terdaftar. Silakan gunakan email lain atau login.")

        # Cek disposable email
        if is_disposable_email(email):
            logger.warning(f"Disposable email rejected: {email}")
            raise ValidationError(
                "Email dari provider sekali pakai tidak diizinkan. "
                "Silakan gunakan email pribadi atau korporat (Gmail, Yahoo, Outlook, dll)."
            )
        
        # Cek domain yang mencurigakan (terlalu banyak subdomain)
        domain = email.split("@")[-1]
        if domain.count(".") >= 3:
            logger.warning(f"Suspicious email domain: {email}")
            raise ValidationError("Domain email tidak valid.")

        logger.info(f"Email validated: {email}")
        return email

    def clean_username(self, username, shallow=False):
        """
        Validasi username: auto-generate dari email jika kosong, enforce rules.

        Rules:
        - Minimal 3 karakter
        - Hanya alphanumeric + underscore
        - Not bot-generated pattern
        - Unique (via parent class)

        Args:
            username (str): Username to validate
            shallow (bool): Shallow validation (skip DB checks)

        Returns:
            str: Cleaned username

        Raises:
            ValidationError: Jika username invalid atau suspicious
        """
        # Auto-generate dari email jika kosong
        if not username or username.strip() == "":
            try:
                email = self.request.POST.get("email", "")
                if email:
                    username = email.split("@")[0]
                    logger.info(f"Username auto-generated dari email: {username}")
            except (AttributeError, IndexError):
                pass

        username = username.lower().strip()

        # Validasi panjang - minimum 5 karakter
        if len(username) < 5:
            raise ValidationError("Username minimal 5 karakter.")

        # Validasi format: alphanumeric + underscore only
        if not all(c.isalnum() or c == "_" for c in username):
            raise ValidationError("Username hanya boleh huruf, angka, dan underscore.")
        
        # Deteksi username yang mencurigakan (bot-generated)
        if is_suspicious_username(username):
            logger.warning(f"Suspicious username rejected: {username}")
            raise ValidationError(
                "Username tidak valid. Gunakan nama yang mudah dibaca, "
                "bukan kombinasi random huruf."
            )

        # Parent validation (unique check, etc)
        return super().clean_username(username, shallow)

    def save_user(self, request, sociallogin=None, form=None, commit=True):
        """
        Buat user & auto-create UserProfile.

        Args:
            request: HTTP request
            sociallogin: Social login object (if social signup)
            form: Signup form
            commit (bool): Save to DB

        Returns:
            User: Created user object
        """
        user = super().save_user(request, sociallogin, form, commit=False)

        if commit:
            user.save()

            # Auto-create UserProfile
            try:
                from .models import UserProfile

                profile, created = UserProfile.objects.get_or_create(user=user)
                if created:
                    logger.info(f"UserProfile auto-created for user: {user.email}")
            except Exception as e:
                logger.error(f"Error creating UserProfile for {user.email}: {str(e)}")

        logger.info(f"User created: {user.email} (username: {user.username})")
        return user

    def get_login_redirect_url(self, request):
        """
        Redirect URL setelah login berhasil.

        - Staff/admin → /admin/
        - Regular user → /accounts/profile/ (profile page dengan popup form untuk update data)

        Args:
            request: HTTP request

        Returns:
            str: Redirect URL
        """
        # Debug session state on social/form login response
        session_key = getattr(request.session, "session_key", None)
        session_exists = request.session.exists(session_key) if session_key else None
        logger.info(
            "[OAUTH-DEBUG] is_secure=%s | xfp=%s | session_key=%s | exists=%s | modified=%s",
            request.is_secure(),
            request.META.get("HTTP_X_FORWARDED_PROTO"),
            session_key,
            session_exists,
            getattr(request.session, "modified", None),
        )

        if request.user.is_staff:
            logger.info(f"Admin login redirect: {request.user.email}")
            return "/admin/"

        logger.info(f"User login redirect to profile: {request.user.email}")
        return "/accounts/profile/"

    def get_signup_redirect_url(self, request):
        """
        Redirect URL setelah signup berhasil.

        Redirect ke profile page dimana user bisa lengkapi profil via popup form.

        Args:
            request: HTTP request

        Returns:
            str: Redirect URL
        """
        user = request.user
        logger.info(f"User signup redirect to profile: {user.email}")
        return "/accounts/profile/"


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter untuk social login (Google, GitHub, etc).

    Fitur:
    - Handle existing email dari social provider
    - Auto-generate username dari social data
    - Anti-spam: disposable email blacklist
    - Auto-create UserProfile
    """

    def pre_social_login(self, request, sociallogin):
        """
        Hook sebelum social login diproses.
        Block suspicious signups even from social providers.
        """
        # Skip jika user sudah ada
        if sociallogin.is_existing:
            return
        
        # IP-based rate limiting untuk social login
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        cache_key = f"social_signup_limit_{ip}"
        signup_count = cache.get(cache_key, 0)
        
        if signup_count >= 3:  # Max 3 social signups per IP per hour
            logger.warning(f"[SOCIAL RATE LIMIT] IP {ip} blocked - too many signups")
            raise ValidationError("Terlalu banyak percobaan signup. Silakan coba lagi nanti.")
        
        # Get email and username dari social data
        email = sociallogin.account.extra_data.get("email", "")
        username = sociallogin.account.extra_data.get("username", "") or \
                   sociallogin.account.extra_data.get("login", "") or \
                   (email.split("@")[0] if email else "")
        
        # Block disposable email
        if email and is_disposable_email(email):
            logger.warning(f"[SOCIAL BLOCK] Disposable email: {email} from {sociallogin.account.provider}")
            raise ValidationError("Email dari provider sekali pakai tidak diizinkan.")
        
        # NOTE: Suspicious username check removed from here.
        # populate_user() will handle invalid usernames gracefully by
        # generating a fallback username (user_xxxxxx) instead of blocking.
        
        # Increment rate limit counter
        cache.set(cache_key, signup_count + 1, 3600)  # 1 hour TTL
        
        # Log semua signup attempts untuk monitoring
        logger.warning(f"[SOCIAL SIGNUP] {email} | {username} | {sociallogin.account.provider} | IP: {ip}")

        # Cek apakah email sudah ada di sistem
        try:
            email = sociallogin.account.extra_data.get("email", "")
            if not email:
                return

            user = User.objects.get(email=email)

            # Connect social account ke existing user
            sociallogin.connect(request, user)
            logger.info(
                f"Social account {sociallogin.account.provider} connected to existing user: {email}"
            )

        except User.DoesNotExist:
            # User baru, akan dibuat di populate_user
            pass
        except Exception as e:
            logger.error(f"Error in pre_social_login: {str(e)}")

    def populate_user(self, request, sociallogin, data):
        """
        Populate user data dari social provider dengan validasi ketat.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Get proposed username
        email = data.get("email", "")
        proposed_username = data.get("username", "") or data.get("login", "")
        
        if not proposed_username and email:
            proposed_username = email.split("@")[0]
        
        # CRITICAL: Validate username before accepting
        if proposed_username:
            proposed_username = proposed_username.lower().strip()
            
            # Reject suspicious usernames
            if is_suspicious_username(proposed_username):
                logger.error(f"[POPULATE BLOCK] Generated username {proposed_username} is suspicious")
                # Use email-based fallback dengan hash
                import hashlib
                email_hash = hashlib.md5(email.encode()).hexdigest()[:6]
                proposed_username = f"user_{email_hash}"
            
            # Ensure minimum length and valid format
            if len(proposed_username) < 5:
                import hashlib
                email_hash = hashlib.md5(email.encode()).hexdigest()[:6]
                proposed_username = f"user_{email_hash}"
            
            # Check alphanumeric + underscore only
            if not all(c.isalnum() or c == "_" for c in proposed_username):
                proposed_username = re.sub(r'[^a-z0-9_]', '', proposed_username)
                if len(proposed_username) < 5:
                    import hashlib
                    email_hash = hashlib.md5(email.encode()).hexdigest()[:6]
                    proposed_username = f"user_{email_hash}"
            
            user.username = proposed_username
            logger.info(f"Username set dari social: {proposed_username}")
        
        # Set names
        if data.get("first_name"):
            user.first_name = data["first_name"]
        if data.get("last_name"):
            user.last_name = data["last_name"]
        
        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Simpan user dari social login & auto-create UserProfile.

        Args:
            request: HTTP request
            sociallogin: Social login object
            form: Form (if any)

        Returns:
            User: Saved user object
        """
        user = super().save_user(request, sociallogin, form)

        # Auto-create UserProfile
        try:
            from .models import UserProfile

            profile, created = UserProfile.objects.get_or_create(user=user)
            if created:
                logger.info(f"UserProfile auto-created for social user: {user.email}")
        except Exception as e:
            logger.error(f"Error creating UserProfile for {user.email}: {str(e)}")

        logger.info(f"Social user saved: {user.email} (provider: {sociallogin.account.provider})")
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        """
        Redirect URL setelah social account di-connect.

        Args:
            request: HTTP request
            socialaccount: Social account object

        Returns:
            str: Redirect URL
        """
        logger.info(
            f"Social account {socialaccount.provider} connected for user: {request.user.email}"
        )
        return "/accounts/profile/"

    def get_app(self, request, provider, client_id=None):
        """
        Get social app configuration.

        Override untuk custom app handling jika diperlukan.

        Args:
            request: HTTP request
            provider (str): Provider name (google, github, etc)
            client_id (str): Client ID (optional)

        Returns:
            SocialApp: Social app object
        """
        app = super().get_app(request, provider, client_id)
        logger.debug(f"Social app loaded: {provider}")
        return app
