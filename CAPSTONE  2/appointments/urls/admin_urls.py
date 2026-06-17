from django.urls import path
from appointments.views import admin_views as v

app_name = 'admin_panel'

urlpatterns = [
    path('',                          v.admin_dashboard,    name='dashboard'),
    path('users/',                    v.user_list,          name='user_list'),
    path('users/create/',             v.user_create,        name='user_create'),
    path('users/<int:pk>/edit/',      v.user_edit,          name='user_edit'),
    path('users/<int:pk>/delete/',    v.user_delete,        name='user_delete'),
    path('appointments/',             v.admin_appointment_list, name='appointment_list'),
    path('feedback/',                 v.admin_feedback_list, name='feedback_list'),
]
