from django.urls import path
from appointments.views import doctor_views as v

app_name = 'doctor'

urlpatterns = [
    path('',                                        v.doctor_dashboard,          name='dashboard'),
    path('schedule/',                               v.schedule_list,             name='schedule_list'),
    path('schedule/add/',                           v.schedule_add,              name='schedule_add'),
    path('schedule/<int:pk>/edit/',                 v.schedule_edit,             name='schedule_edit'),
    path('schedule/<int:pk>/delete/',               v.schedule_delete,           name='schedule_delete'),
    path('appointments/',                           v.doctor_appointment_list,   name='appointment_list'),
    path('appointments/<int:pk>/detail/',           v.appointment_detail,        name='appointment_detail'),
    path('appointments/<int:pk>/accept/',           v.appointment_accept,        name='appointment_accept'),
    path('appointments/<int:pk>/decline/',          v.appointment_decline,       name='appointment_decline'),
    path('appointments/<int:pk>/reschedule/',       v.appointment_reschedule,    name='appointment_reschedule'),
    path('appointments/<int:pk>/complete/',         v.appointment_complete,      name='appointment_complete'),
    path('appointments/<int:pk>/results/',          v.add_consultation_results,  name='add_results'),
    path('appointments/<int:pk>/results/prescription/', v.add_prescription,      name='add_prescription'),
    path('patients/',                               v.doctor_patient_list,       name='patient_list'),
    path('patients/<int:patient_id>/quickview/',    v.patient_quickview,         name='patient_quickview'),
    path('patients/<int:patient_id>/records/',      v.doctor_patient_records,    name='patient_records'),
    path('notifications/',                          v.doctor_notifications,      name='notifications'),
]
