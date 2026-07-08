from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',        views.login_view,        name='login'),
    path('logout/',       views.logout_view,        name='logout'),
    path('register/',     views.register_view,      name='register'),
    path('signup/',       views.signup_redirect,    name='signup'),
    path('profile/',      views.profile_view,       name='profile_view'),
    path('profile/edit/', views.profile_edit_view,  name='profile_edit'),
    path('settings/',     views.settings_view,      name='settings'),
    path('help/',         views.help_view,          name='help'),
]
