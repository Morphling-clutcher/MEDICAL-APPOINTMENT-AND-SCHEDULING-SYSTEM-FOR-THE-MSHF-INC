from django.urls import path
from appointments.views import secretary_views as v

app_name = 'secretary'

urlpatterns = [
    path('',                                         v.secretary_dashboard,       name='dashboard'),
    path('dashboard/data/',                          v.secretary_dashboard_data,  name='dashboard_data'),
    path('appointments/',                            v.secretary_appointment_list, name='appointment_list'),
    path('appointments/<int:pk>/detail/',            v.appointment_detail,        name='appointment_detail'),
    path('appointments/<int:pk>/assign-time/',       v.assign_appointment_time,   name='assign_time'),
    path('appointments/<int:pk>/occupied-times/',    v.get_occupied_times,        name='occupied_times'),
    path('appointments/<int:pk>/confirm/',           v.appointment_confirm,       name='appointment_confirm'),
    path('appointments/<int:pk>/complete/',          v.appointment_complete,      name='appointment_complete'),
    path('appointments/<int:pk>/reschedule/approve/', v.appointment_reschedule_approve, name='reschedule_approve'),
    path('appointments/<int:pk>/reschedule/reject/',  v.appointment_reschedule_reject,  name='reschedule_reject'),
    path('appointments/<int:pk>/reschedule/',        v.appointment_reschedule,    name='reschedule'),
    path('appointments/<int:pk>/cancel/',            v.appointment_cancel,        name='appointment_cancel'),
    path('patients/<int:patient_id>/vitals/add/',    v.vitals_add,                name='vitals_add'),
    path('schedules/',                               v.view_all_schedules,        name='schedule_view'),
    path('schedules/grid/',                          v.schedule_grid_partial,     name='schedule_grid_partial'),
    path('patients/',                                v.secretary_patient_list,    name='patient_list'),
    path('patients/<int:patient_id>/quickview/',     v.patient_quickview,         name='patient_quickview'),
    path('patients/<int:patient_id>/records/',       v.secretary_patient_records, name='patient_records'),
    path('notifications/',                           v.secretary_notifications,   name='notifications'),
]
