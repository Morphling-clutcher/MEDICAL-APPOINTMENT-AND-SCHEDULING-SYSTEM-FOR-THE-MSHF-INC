from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('',                    views.notification_list,     name='list'),
    path('panel/',              views.notification_panel,    name='panel'),
    path('<int:pk>/detail/',    views.notification_detail,   name='detail'),
    path('<int:pk>/read/',      views.mark_read,             name='mark_read'),
    path('<int:pk>/dismiss/',   views.notification_dismiss,  name='dismiss'),
    path('mark-all-read/',      views.mark_all_read,         name='mark_all_read'),
]

