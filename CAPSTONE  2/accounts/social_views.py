"""Sign in / sign up with Google (patients only).

Server-side Authorization Code flow: /social/<provider>/start/ sends the
browser to the provider's consent screen, /social/<provider>/callback/
receives the one-time code and turns it into a logged-in session.

Hard rule enforced here: social login can only ever create or log into
PATIENT accounts. Doctor/secretary/admin accounts are created by admins and
must keep using username/password — even a perfect verified-email match on a
staff account is refused rather than linked.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse

from .forms import _generate_prefixed_username
from .models import CustomUser, PatientProfile, SocialAccount
from .social_auth import (
    PROVIDERS, SocialAuthError, build_authorization_url, fetch_user_profile,
    generate_state, provider_is_configured,
)
from .views import _notify_admins, _role_redirect

STATE_SESSION_KEY = 'social_auth_state'

# login() normally learns the backend from authenticate(); social logins skip
# authenticate() (the provider already vouched for the user), so name the
# backend explicitly.
AUTH_BACKEND = 'django.contrib.auth.backends.ModelBackend'


def _redirect_uri(request, provider):
    return request.build_absolute_uri(reverse('accounts:social_callback', args=[provider]))


def social_start(request, provider):
    if provider not in PROVIDERS:
        messages.error(request, 'Unsupported sign-in provider.')
        return redirect('accounts:login')
    if request.user.is_authenticated:
        return _role_redirect(request.user)
    if not provider_is_configured(provider):
        messages.error(request, f'Sign-in with {provider.title()} is not available right now.')
        return redirect('accounts:login')

    state = generate_state()
    request.session[STATE_SESSION_KEY] = {'provider': provider, 'value': state}
    return redirect(build_authorization_url(provider, _redirect_uri(request, provider), state))


def social_callback(request, provider):
    if provider not in PROVIDERS or not provider_is_configured(provider):
        messages.error(request, 'Unsupported sign-in provider.')
        return redirect('accounts:login')

    # The user clicked "Cancel" on the consent screen — that's a choice, not
    # a failure.
    if request.GET.get('error'):
        messages.info(request, 'Sign-in was cancelled.')
        return redirect('accounts:login')

    # State is single-use: pop it so a replayed callback URL can't be
    # accepted twice, and require an exact provider + value match.
    expected = request.session.pop(STATE_SESSION_KEY, None)
    state = request.GET.get('state', '')
    code = request.GET.get('code', '')
    if (
        not expected or not state or not code
        or expected.get('provider') != provider
        or expected.get('value') != state
    ):
        messages.error(request, 'Sign-in session expired or was invalid. Please try again.')
        return redirect('accounts:login')

    try:
        profile = fetch_user_profile(provider, code, _redirect_uri(request, provider))
    except SocialAuthError as exc:
        messages.error(request, exc.message)
        return redirect('accounts:login')

    # Case A — this external identity is already linked: log straight in.
    existing_link = SocialAccount.objects.filter(
        provider=provider, provider_user_id=profile['provider_user_id'],
    ).select_related('user').first()
    if existing_link:
        return _log_in(request, existing_link.user)

    email = profile['email']
    if not email:
        messages.warning(
            request,
            f'Your {provider.title()} account did not share an email address, '
            'so we could not sign you in with it. Please create an account below instead.'
        )
        return redirect('accounts:register')
    if not profile['email_verified']:
        # Never create or link on an email the provider itself doesn't
        # vouch for — that's how account takeovers happen.
        messages.warning(
            request,
            f'The email on your {provider.title()} account is not verified, '
            'so we could not sign you in with it. Please create an account below instead.'
        )
        return redirect('accounts:register')

    # Case B — a local account already uses this (verified) email.
    matches = list(CustomUser.objects.filter(email__iexact=email)[:2])
    if len(matches) > 1:
        # Ambiguous — more than one account shares the email. Refuse to
        # guess which one to link.
        messages.error(
            request,
            'An account with this email already exists. Please sign in with your username and password.'
        )
        return redirect('accounts:login')
    if matches:
        user = matches[0]
        if user.role != 'patient':
            # Staff accounts are never reachable via social login, even on
            # a perfect verified-email match.
            messages.error(
                request,
                'This email belongs to a staff account. Please sign in with your username and password.'
            )
            return redirect('accounts:login')
        SocialAccount.objects.create(
            user=user, provider=provider,
            provider_user_id=profile['provider_user_id'], email_at_link=email,
        )
        return _log_in(request, user)

    # Case C — first visit: create a fresh patient account.
    with transaction.atomic():
        user = CustomUser(
            username=_generate_prefixed_username(provider, profile['first_name'], profile['last_name']),
            first_name=profile['first_name'],
            last_name=profile['last_name'],
            email=email,
            role='patient',
        )
        # They authenticate through the provider — leaving no local password
        # means there's nothing to phish or forget.
        user.set_unusable_password()
        user.save()
        PatientProfile.objects.create(user=user)
        SocialAccount.objects.create(
            user=user, provider=provider,
            provider_user_id=profile['provider_user_id'], email_at_link=email,
        )
    _notify_admins(f"New patient account created: {user.get_full_name()} ({user.username}).")
    messages.info(
        request,
        'Welcome to MSHFI! Please complete your profile (address and place of birth) before booking an appointment.'
    )
    return _log_in(request, user)


def _log_in(request, user):
    # login() skips authenticate() here, so replicate ModelBackend's
    # is_active check — a deactivated patient must stay locked out even
    # through a valid Google link.
    if not user.is_active:
        messages.error(request, 'This account has been deactivated. Please contact the clinic.')
        return redirect('accounts:login')
    login(request, user, backend=AUTH_BACKEND)
    return _role_redirect(user)
