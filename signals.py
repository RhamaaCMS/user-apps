import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        pass


def _get_social_account_avatar(user):
    """Return avatar URL from the user's first linked social account."""
    try:
        from allauth.socialaccount.models import SocialAccount

        for provider in ("google", "github"):
            account = SocialAccount.objects.filter(user=user, provider=provider).first()
            if account is None:
                continue
            if provider == "google" and "picture" in account.extra_data:
                return account.extra_data["picture"]
            if provider == "github" and "avatar_url" in account.extra_data:
                return account.extra_data["avatar_url"]
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting social account avatar: %s", exc)
    return None


def _save_avatar_from_url(user, avatar_url):
    """Download *avatar_url* and save it to the Wagtail UserProfile."""
    try:
        import requests
        from django.core.files.base import ContentFile
        from wagtail.users.models import UserProfile as WagtailUserProfile

        response = requests.get(avatar_url, timeout=10)
        if response.status_code != 200:
            return
        wagtail_profile, _ = WagtailUserProfile.objects.get_or_create(user=user)
        old_avatar = wagtail_profile.avatar or None
        wagtail_profile.avatar.save(
            f"avatar_{user.username}.jpg",
            ContentFile(response.content),
            save=True,
        )
        logger.info("Avatar saved for user: %s", user.username)
        if old_avatar:
            try:
                storage = old_avatar.storage
                if storage.exists(old_avatar.name):
                    storage.delete(old_avatar.name)
            except Exception as exc:
                logger.error("Error deleting old avatar: %s", exc)
    except Exception as exc:
        logger.error("Error saving avatar from URL: %s", exc)


@receiver(post_save, sender=User, dispatch_uid="users_set_avatar_on_creation")
def set_profile_picture_on_user_creation(sender, instance, created, **kwargs):
    """Asynchronously fetch social avatar 5 s after the user is created."""
    if not created:
        return
    import threading
    from django.core.cache import cache

    cache_key = f"user_created_{instance.id}"
    if cache.get(cache_key):
        return
    cache.set(cache_key, True, 60)

    def delayed():
        avatar_url = _get_social_account_avatar(instance)
        if avatar_url:
            _save_avatar_from_url(instance, avatar_url)

    threading.Timer(5.0, delayed).start()


try:
    from allauth.socialaccount.signals import social_account_added

    @receiver(social_account_added, dispatch_uid="users_set_avatar_on_social_add")
    def set_profile_picture_on_social_account_added(request, sociallogin, **kwargs):
        """Immediately fetch avatar when a social account is linked."""
        user = sociallogin.user
        avatar_url = None
        account = sociallogin.account
        if account.provider == "google":
            avatar_url = account.extra_data.get("picture")
        elif account.provider == "github":
            avatar_url = account.extra_data.get("avatar_url")
        if avatar_url:
            _save_avatar_from_url(user, avatar_url)

except ImportError:
    pass  # allauth not installed
