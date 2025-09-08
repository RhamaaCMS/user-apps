# models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from wagtail.users.models import UserProfile as WagtailUserProfile

# Fungsi ini masih diperlukan untuk migrasi meskipun kita tidak lagi menggunakannya
def profile_picture_upload_path(instance, filename):
    return f'profile_pictures/{instance.user.id}/{filename}'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    # Menghapus field profile_picture karena akan menggunakan avatar dari Wagtail UserProfile
    # profile_picture = models.ImageField(upload_to=profile_picture_upload_path, blank=True)
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")]
    )
    address = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        # Menghapus logika penghapusan gambar lama karena kita tidak lagi menggunakan field profile_picture
        # if self.pk:
        #     previous = UserProfile.objects.get(pk=self.pk)
        #     if previous.profile_picture and previous.profile_picture != self.profile_picture:
        #         previous.profile_picture.delete(save=False)
        super().save(*args, **kwargs)
        
    @property
    def profile_picture(self):
        """
        Mendapatkan avatar dari Wagtail UserProfile jika ada
        """
        try:
            wagtail_profile = WagtailUserProfile.objects.get(user=self.user)
            if wagtail_profile.avatar:
                return wagtail_profile.avatar
        except WagtailUserProfile.DoesNotExist:
            pass
        return None