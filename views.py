from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from allauth.socialaccount.models import SocialAccount  # Import model untuk akun sosial
from allauth.account.models import EmailAddress  # Import model untuk email
from .forms import UserProfileForm
from .models import UserProfile
from wagtail.users.models import UserProfile as WagtailUserProfile
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.signals import social_account_added

# Konfigurasi logging
logger = logging.getLogger(__name__)

@login_required
def profile_view(request):
    # Ambil objek UserProfile yang terkait dengan user
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        # Buat UserProfile baru jika belum ada
        user_profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        # Form untuk memperbarui profil, termasuk username dari model User
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil berhasil diperbarui.')
            return redirect('profile')  # Redirect ke halaman profil setelah berhasil update
    else:
        # Prepopulate form dengan data dari user dan user profile
        form = UserProfileForm(instance=user_profile)
        form.fields['username'].initial = request.user.username  # Isi awal field username dari model User

    # Ambil akun sosial yang terhubung dengan user
    social_accounts = SocialAccount.objects.filter(user=request.user)

    # Ambil email sekunder yang terdaftar pada user (kecuali email utama)
    secondary_emails = EmailAddress.objects.filter(user=request.user).exclude(primary=True)

    return render(request, 'pages/accounts/profile.html', {
        'form': form,
        'user_profile': user_profile,
        'social_accounts': social_accounts,  # Kirim data akun sosial ke template
        'secondary_emails': secondary_emails,  # Kirim data email sekunder ke template
    })

def public_profile_view(request, username):
    # Cari user berdasarkan username
    user = get_object_or_404(User, username=username)
    
    # Ambil UserProfile terkait
    user_profile = user.userprofile
    
    # Cek apakah profil publik atau tidak
    if not user_profile.is_public:
        raise Http404("This user's profile is not public.")
    
    # Ambil akun sosial yang terhubung
    social_accounts = SocialAccount.objects.filter(user=user)
    
    # Kumpulkan data dari akun sosial
    social_data = []
    for account in social_accounts:
        provider_data = {
            'provider': account.provider,
            'extra_data': account.extra_data,
        }
        
        # Tambahkan data spesifik provider
        if account.provider == 'github':
            provider_data.update({
                'avatar': account.extra_data.get('avatar_url'),
                'company': account.extra_data.get('company'),
                'blog': account.extra_data.get('blog'),
                'location': account.extra_data.get('location'),
                'bio': account.extra_data.get('bio'),
                'public_repos': account.extra_data.get('public_repos'),
                'followers': account.extra_data.get('followers'),
                'following': account.extra_data.get('following'),
            })
        elif account.provider == 'google':
            provider_data.update({
                'avatar': account.extra_data.get('picture'),
                'email': account.extra_data.get('email'),
                'name': account.extra_data.get('name'),
                'given_name': account.extra_data.get('given_name'),
                'family_name': account.extra_data.get('family_name'),
            })
        
        social_data.append(provider_data)
    
    return render(request, 'pages/accounts/public_profile.html', {
        'user': user,
        'user_profile': user_profile,
        'social_data': social_data,
    })

# Fungsi untuk mengambil foto profil dari akun sosial
def get_social_account_avatar(user):
    try:
        # Cek apakah user memiliki akun sosial
        social_accounts = SocialAccount.objects.filter(user=user)
        if not social_accounts.exists():
            return None
        
        # Prioritaskan Google, lalu GitHub
        for provider in ['google', 'github']:
            for account in social_accounts.filter(provider=provider):
                if provider == 'google' and 'picture' in account.extra_data:
                    return account.extra_data['picture']
                elif provider == 'github' and 'avatar_url' in account.extra_data:
                    return account.extra_data['avatar_url']
        
        return None
    except Exception as e:
        logger.error(f"Error getting social account avatar: {str(e)}")
        return None

# Signal handler untuk mengambil foto profil dari akun sosial saat user mendaftar
@receiver(post_save, sender=User)
def set_profile_picture_on_user_creation(sender, instance, created, **kwargs):
    if created:
        try:
            # Tunggu sebentar untuk memastikan akun sosial sudah terhubung
            from django.core.cache import cache
            cache_key = f"user_created_{instance.id}"
            if not cache.get(cache_key):
                cache.set(cache_key, True, 60)  # Set cache untuk 60 detik
                
                # Jadwalkan tugas untuk dijalankan setelah beberapa detik
                from django.core.management import call_command
                import threading
                
                def delayed_task():
                    try:
                        # Cek apakah user memiliki akun sosial
                        avatar_url = get_social_account_avatar(instance)
                        if avatar_url:
                            # Import required libraries
                            import requests
                            from django.core.files.base import ContentFile
                            
                            # Dapatkan atau buat Wagtail UserProfile
                            wagtail_profile, created = WagtailUserProfile.objects.get_or_create(user=instance)
                            
                            # Download the image
                            logger.info(f"Downloading image from: {avatar_url}")
                            response = requests.get(avatar_url)
                            if response.status_code == 200:
                                # Create a ContentFile from the downloaded image
                                image_name = f"avatar_{instance.username}.jpg"
                                
                                # Simpan avatar ke Wagtail UserProfile
                                wagtail_profile.avatar.save(
                                    image_name,
                                    ContentFile(response.content),
                                    save=True
                                )
                                logger.info(f"Avatar saved successfully for user: {instance.username}")
                    except Exception as e:
                        logger.error(f"Error in delayed task: {str(e)}")
                
                # Jalankan tugas setelah 5 detik
                t = threading.Timer(5.0, delayed_task)
                t.start()
        except Exception as e:
            logger.error(f"Error setting profile picture on user creation: {str(e)}")

# Signal handler untuk mengambil foto profil saat akun sosial ditambahkan
@receiver(social_account_added)
def set_profile_picture_on_social_account_added(request, sociallogin, **kwargs):
    try:
        user = sociallogin.user
        avatar_url = None
        
        # Ambil URL avatar dari akun sosial yang baru ditambahkan
        if sociallogin.account.provider == 'google' and 'picture' in sociallogin.account.extra_data:
            avatar_url = sociallogin.account.extra_data['picture']
        elif sociallogin.account.provider == 'github' and 'avatar_url' in sociallogin.account.extra_data:
            avatar_url = sociallogin.account.extra_data['avatar_url']
        
        if avatar_url:
            # Import required libraries
            import requests
            from django.core.files.base import ContentFile
            
            # Dapatkan atau buat Wagtail UserProfile
            wagtail_profile, created = WagtailUserProfile.objects.get_or_create(user=user)
            
            # Simpan referensi ke avatar lama jika ada
            old_avatar = None
            if not created and wagtail_profile.avatar:
                old_avatar = wagtail_profile.avatar
            
            # Download the image
            logger.info(f"Downloading image from: {avatar_url}")
            response = requests.get(avatar_url)
            if response.status_code == 200:
                # Create a ContentFile from the downloaded image
                image_name = f"avatar_{user.username}.jpg"
                
                # Simpan avatar ke Wagtail UserProfile
                wagtail_profile.avatar.save(
                    image_name,
                    ContentFile(response.content),
                    save=True
                )
                logger.info(f"Avatar saved successfully for user: {user.username}")
                
                # Hapus avatar lama setelah menyimpan yang baru
                if old_avatar:
                    try:
                        storage = old_avatar.storage
                        if storage.exists(old_avatar.name):
                            storage.delete(old_avatar.name)
                            logger.info(f"Deleted old avatar: {old_avatar.name}")
                    except Exception as e:
                        logger.error(f"Error deleting old avatar: {str(e)}")
    except Exception as e:
        logger.error(f"Error setting profile picture on social account added: {str(e)}")