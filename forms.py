from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from wagtail.users.models import UserProfile as WagtailUserProfile
import logging
import os
from django.conf import settings

# Konfigurasi logging
logger = logging.getLogger(__name__)

class UserProfileForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True, label="Username")
    avatar = forms.ImageField(required=False, label="Foto Profil")

    class Meta:
        model = UserProfile
        fields = ['bio', 'phone_number', 'address']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mengambil avatar dari Wagtail UserProfile jika ada
        if self.instance and self.instance.user:
            try:
                wagtail_profile = WagtailUserProfile.objects.get(user=self.instance.user)
                if wagtail_profile.avatar:
                    self.fields['avatar'].initial = wagtail_profile.avatar
            except WagtailUserProfile.DoesNotExist:
                pass

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # Validasi: cek apakah username sudah digunakan oleh user lain
        if User.objects.filter(username=username).exclude(pk=self.instance.user.pk).exists():
            raise forms.ValidationError('Username sudah digunakan oleh pengguna lain.')
        return username

    def save(self, commit=True):
        user = self.instance.user
        user.username = self.cleaned_data['username']
        user.save()
        
        # Menyimpan avatar ke Wagtail UserProfile
        avatar = self.cleaned_data.get('avatar')
        
        logger.info(f"Form save - Avatar: {avatar}")
        
        try:
            wagtail_profile, created = WagtailUserProfile.objects.get_or_create(user=user)
            old_avatar = None
            
            # Simpan referensi ke avatar lama jika ada
            if not created and wagtail_profile.avatar:
                old_avatar = wagtail_profile.avatar
                old_avatar_path = old_avatar.path if hasattr(old_avatar, 'path') else None
                logger.info(f"Existing avatar found for user {user.username}: {old_avatar_path}")
            
            # Jika ada avatar yang diupload, gunakan itu
            if avatar:
                logger.info(f"Saving uploaded avatar for user: {user.username}")
                wagtail_profile.avatar = avatar
                wagtail_profile.save()
                
                # Hapus avatar lama setelah menyimpan yang baru
                if old_avatar and old_avatar != avatar:
                    try:
                        storage = old_avatar.storage
                        if storage.exists(old_avatar.name):
                            storage.delete(old_avatar.name)
                            logger.info(f"Deleted old avatar: {old_avatar.name}")
                    except Exception as e:
                        logger.error(f"Error deleting old avatar: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error saving avatar: {str(e)}")
            
        return super().save(commit=commit)
