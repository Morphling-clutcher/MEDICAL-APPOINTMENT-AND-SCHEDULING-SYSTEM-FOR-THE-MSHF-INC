# Social Login Setup (Sign in / Sign up with Google)

Patients can sign in or create an account with Google from the login page.
This is patient-only by design: doctor, secretary, and admin accounts are
created by admins and always use username + password — a Google login will
never create or link to a staff account, even when the email matches.

No extra packages are involved. The flow is a hand-rolled server-side
OAuth 2.0 Authorization Code exchange in `accounts/social_auth.py` /
`accounts/social_views.py`, using only the Python standard library.

## Environment variables

Add these to the project's `.env` file (same file the database/email
settings already use):

```env
GOOGLE_OAUTH_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
```

Behavior when they're missing: nothing breaks. The Google button on the
login/register card simply stays in its disabled "Coming soon" state, and
the `/accounts/social/google/...` URLs refuse to start a sign-in. Set both
variables and restart the server to light the button up.

## Google Cloud Console walkthrough

1. Go to <https://console.cloud.google.com/> and create (or select) a
   project, e.g. "MSHFI Appointment System".
2. **OAuth consent screen** (APIs & Services → OAuth consent screen):
   - User type: **External**.
   - App name, support email, developer contact: fill in the clinic's info.
   - Scopes: leave the defaults. This integration only uses
     `openid`, `email`, and `profile` — all non-sensitive, so **no Google
     verification review is required** and there is no waiting period.
   - You can stay in "Testing" while developing (add your own Gmail as a
     test user), then click **Publish app** when ready — for these scopes
     publishing is immediate.
3. **Create the OAuth client** (APIs & Services → Credentials → Create
   Credentials → OAuth client ID):
   - Application type: **Web application**.
   - Name: e.g. "MSHFI web login".
   - **Authorized redirect URIs** — add one entry per host you serve from,
     each ending in exactly `/accounts/social/google/callback/`:
     - `http://127.0.0.1:8000/accounts/social/google/callback/` (dev)
     - `http://localhost:8000/accounts/social/google/callback/` (dev)
     - `https://<your-production-domain>/accounts/social/google/callback/`
   - The path must match character-for-character, including the trailing
     slash — a mismatch produces Google's `redirect_uri_mismatch` error.
4. Copy the generated **Client ID** and **Client secret** into `.env` as
   shown above, restart the server, and the Google button appears on
   `/accounts/login/`.

## How sign-in behaves (for reference)

- A Google account that was used here before logs straight in (matched by
  Google's stable user ID, never by email).
- A verified Google email that matches an existing **patient** account gets
  linked to it automatically.
- A verified Google email that matches a **staff** account is refused with
  "please sign in with your username and password".
- Otherwise a new patient account is created (username like
  `google-juan-delacruz`, no local password) and admins get the same
  "new patient account" notification as manual self-registration.
- Google never supplies an address or place of birth, so new social
  patients are redirected to profile edit the first time they try to book
  an appointment; booking stays blocked until both fields are filled in.

## Facebook (deferred)

The Facebook button is intentionally still "Coming soon". Meta's
requirements make it a timeline dependency rather than a quick win:

- Facebook Login only accepts **HTTPS** redirect URIs outside of
  localhost — the app must already be deployed behind TLS.
- The Meta app must pass **App Review / be switched to Live Mode** before
  anyone other than registered testers can log in with it.

Ship Google first (done); enable Facebook later with:

1. Code: add `'facebook'` to `PROVIDERS` in `accounts/social_auth.py` and
   implement its two branches there (authorization URL:
   `https://www.facebook.com/v19.0/dialog/oauth` with
   `scope=email,public_profile`; token + profile via the Graph API
   `oauth/access_token` and `/me?fields=id,first_name,last_name,email`).
   Everything else — model, URLs, views, template button — is already
   provider-generic and picks Facebook up automatically.
2. Settings: add `FACEBOOK_OAUTH_APP_ID` / `FACEBOOK_OAUTH_APP_SECRET` env
   reads in `mshfi/settings.py` and teach `provider_is_configured` about
   them.
3. Meta for Developers (<https://developers.facebook.com/>): create an app,
   add the **Facebook Login** product, set the Valid OAuth Redirect URI to
   `https://<your-production-domain>/accounts/social/facebook/callback/`,
   then complete App Review and switch the app to Live Mode.
