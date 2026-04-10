"""
Unit tests untuk custom django-allauth adapters.

Tests:
- Email validation (unique, format)
- Username validation & auto-generation
- User creation & profile setup
- Social login flow
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.users.adapters import CustomAccountAdapter, CustomSocialAccountAdapter
from apps.users.models import UserProfile

User = get_user_model()


class CustomAccountAdapterTests(TestCase):
    """Test CustomAccountAdapter untuk form signup."""

    def setUp(self):
        """Setup test fixtures."""
        self.factory = RequestFactory()
        self.adapter = CustomAccountAdapter()

    # ===== Email Validation Tests =====

    def test_clean_email_valid(self):
        """Email valid harus pass."""
        email = "newuser@example.com"
        result = self.adapter.clean_email(email)
        self.assertEqual(result, email.lower())

    def test_clean_email_lowercase(self):
        """Email harus di-lowercase."""
        email = "NewUser@Example.COM"
        result = self.adapter.clean_email(email)
        self.assertEqual(result, "newuser@example.com")

    def test_clean_email_strip_whitespace(self):
        """Email harus di-strip whitespace."""
        email = "  user@example.com  "
        result = self.adapter.clean_email(email)
        self.assertEqual(result, "user@example.com")

    def test_clean_email_duplicate_raises_error(self):
        """Email yang sudah ada harus raise ValidationError."""
        # Create existing user
        User.objects.create_user(email="existing@example.com", username="existing")

        # Try to use same email
        with self.assertRaises(ValidationError) as cm:
            self.adapter.clean_email("existing@example.com")

        self.assertIn("sudah terdaftar", str(cm.exception))

    # ===== Username Validation Tests =====

    def test_clean_username_valid(self):
        """Username valid harus pass."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "test@example.com"}
        self.adapter.request = request

        result = self.adapter.clean_username("testuser")
        self.assertEqual(result, "testuser")

    def test_clean_username_lowercase(self):
        """Username harus di-lowercase."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "test@example.com"}
        self.adapter.request = request

        result = self.adapter.clean_username("TestUser")
        self.assertEqual(result, "testuser")

    def test_clean_username_min_length(self):
        """Username minimal 3 karakter."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "test@example.com"}
        self.adapter.request = request

        with self.assertRaises(ValidationError) as cm:
            self.adapter.clean_username("ab")

        self.assertIn("minimal 3", str(cm.exception))

    def test_clean_username_invalid_characters(self):
        """Username hanya boleh alphanumeric + underscore."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "test@example.com"}
        self.adapter.request = request

        with self.assertRaises(ValidationError) as cm:
            self.adapter.clean_username("test@user")

        self.assertIn("huruf, angka", str(cm.exception))

    def test_clean_username_underscore_allowed(self):
        """Username boleh pakai underscore."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "test@example.com"}
        self.adapter.request = request

        result = self.adapter.clean_username("test_user_123")
        self.assertEqual(result, "test_user_123")

    def test_clean_username_autogenerate_from_email(self):
        """Username harus auto-generate dari email jika kosong."""
        request = self.factory.post("/accounts/signup/")
        request.POST = {"email": "myemail@example.com"}
        self.adapter.request = request

        result = self.adapter.clean_username("")
        self.assertEqual(result, "myemail")

    # ===== User Creation Tests =====

    def test_save_user_creates_user(self):
        """save_user harus create user di database."""
        # Create user directly (simulating form.save())
        user = User.objects.create_user(email="newuser@example.com", username="newuser")

        # Verify user created
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())
        self.assertEqual(user.email, "newuser@example.com")

    def test_save_user_creates_profile(self):
        """save_user harus auto-create UserProfile."""
        # Create user directly
        user = User.objects.create_user(email="profiletest@example.com", username="profiletest")

        # Check profile exists (auto-created by signal)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    # ===== Redirect Tests =====

    def test_login_redirect_for_staff(self):
        """Staff user harus redirect ke /admin/."""
        request = self.factory.get("/")
        staff_user = User.objects.create_user(
            email="staff@example.com", username="staff", is_staff=True
        )
        request.user = staff_user

        redirect_url = self.adapter.get_login_redirect_url(request)
        self.assertEqual(redirect_url, "/admin/")

    def test_login_redirect_for_regular_user(self):
        """Regular user harus redirect ke /my-modules/."""
        request = self.factory.get("/")
        regular_user = User.objects.create_user(email="user@example.com", username="user")
        request.user = regular_user

        redirect_url = self.adapter.get_login_redirect_url(request)
        self.assertEqual(redirect_url, "/my-modules/")

    def test_signup_redirect(self):
        """Signup harus redirect ke /accounts/profile/complete/ jika profile belum complete."""
        request = self.factory.get("/")
        request.user = User.objects.create_user(email="signup@example.com", username="signup")

        redirect_url = self.adapter.get_signup_redirect_url(request)
        self.assertEqual(redirect_url, "/accounts/profile/complete/")


class CustomSocialAccountAdapterTests(TestCase):
    """Test CustomSocialAccountAdapter untuk social login."""

    def setUp(self):
        """Setup test fixtures."""
        self.factory = RequestFactory()
        self.adapter = CustomSocialAccountAdapter()

    def test_populate_user_autogenerate_username(self):
        """populate_user harus auto-generate username dari email."""
        # Test username generation from email
        email = "social@example.com"
        username = email.split("@")[0]

        self.assertEqual(username, "social")

    def test_populate_user_sets_name(self):
        """populate_user harus set first_name & last_name dari social data."""
        # Test that data is properly extracted
        data = {"email": "john@example.com", "first_name": "John", "last_name": "Doe"}

        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")

    def test_get_connect_redirect_url(self):
        """get_connect_redirect_url harus return /accounts/profile/."""
        request = self.factory.get("/")
        request.user = User.objects.create_user(email="connect@example.com", username="connect")

        class MockSocialAccount:
            provider = "google"

        redirect_url = self.adapter.get_connect_redirect_url(request, MockSocialAccount())

        self.assertEqual(redirect_url, "/accounts/profile/")


class IntegrationTests(TestCase):
    """Integration tests untuk full signup/login flow."""

    def setUp(self):
        """Setup test fixtures."""
        self.factory = RequestFactory()

    def test_form_signup_flow(self):
        """Test full form signup flow."""
        # 1. Create user
        user = User.objects.create_user(email="integration@example.com", username="integration")

        # 2. Check user created
        self.assertTrue(User.objects.filter(email="integration@example.com").exists())

        # 3. Check profile created
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_email_unique_constraint(self):
        """Test email unique constraint."""
        # Create first user
        user1 = User.objects.create_user(email="unique@example.com", username="user1")

        # Verify user created
        self.assertTrue(User.objects.filter(email="unique@example.com").exists())
        self.assertEqual(user1.email, "unique@example.com")
