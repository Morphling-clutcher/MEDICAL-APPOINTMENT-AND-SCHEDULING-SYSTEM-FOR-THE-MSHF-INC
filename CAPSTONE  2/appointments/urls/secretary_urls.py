from django.urls import path
from appointments.views import secretary_views as v

app_name = 'secretary'

urlpatterns = [
    path('',                                         v.secretary_dashboard,       name='dashboard'),
    path('appointments/',                            v.secretary_appointment_list, name='appointment_list'),
    path('appointments/<int:pk>/detail/',            v.appointment_detail,        name='appointment_detail'),
    path('appointments/<int:pk>/approve/',           v.appointment_approve,       name='appointment_approve'),
    path('appointments/<int:pk>/cancel/',            v.appointment_cancel,        name='appointment_cancel'),
    path('walk-in/register/',                        v.walkin_register,           name='walkin_register'),
    path('walk-in/<int:patient_id>/vitals/add/',     v.vitals_add,                name='vitals_add'),
    path('schedules/',                               v.view_all_schedules,        name='schedule_view'),
    path('patients/',                                v.secretary_patient_list,    name='patient_list'),
    path('patients/<int:patient_id>/quickview/',     v.patient_quickview,         name='patient_quickview'),
    path('patients/<int:patient_id>/records/',       v.secretary_patient_records, name='patient_records'),
    path('notifications/',                           v.secretary_notifications,   name='notifications'),
]
