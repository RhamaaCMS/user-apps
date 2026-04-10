import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import UserProfileForm
from .models import UserProfile

logger = logging.getLogger(__name__)


@login_required
def profile_view(request):
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil berhasil diperbarui.")
            return redirect("users:profile")
        # On validation error fall through to render with errors
    else:
        form = UserProfileForm(instance=user_profile)
        form.fields["username"].initial = request.user.username

    user = request.user
    social_accounts = SocialAccount.objects.filter(user=user)
    secondary_emails = EmailAddress.objects.filter(user=user).exclude(primary=True)

    return render(
        request,
        "pages/users/profile.html",
        {
            "user": user,
            "user_profile": user_profile,
            "form": form,
            "social_accounts": social_accounts,
            "secondary_emails": secondary_emails,
        },
    )


