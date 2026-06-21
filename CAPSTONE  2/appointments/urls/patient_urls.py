from django.urls import path
from appointments.views import patient_views as v

app_name = 'patient'

urlpatterns = [
    path('',                                    v.patient_dashboard,      name='dashboard'),
    path('appointments/',                        v.appointment_list,       name='appointment_list'),
    path('appointments/book/',                   v.book_step1,             name='book_step1'),
    path('doctors/<int:doctor_id>/',              v.doctor_profile_view,    name='doctor_profile'),
    path('appointments/book/<int:doctor_id>/slots/', v.book_step2_slots,  name='book_step2'),
    path('appointments/book/<int:doctor_id>/slots/partial/', v.book_step2_slots_partial, name='book_step2_partial'),
    path('appointments/book/confirm/',           v.book_step3_confirm,     name='book_confirm'),
    path('appointments/<int:pk>/detail/',        v.appointment_detail,     name='appointment_detail'),
    path('appointments/<int:pk>/reschedule/',    v.reschedule_appointment, name='reschedule'),
    path('appointments/<int:pk>/cancel/',        v.cancel_appointment,     name='cancel'),
    path('records/',                             v.medical_records,        name='medical_records'),
    path('records/<int:pk>/detail/',             v.medical_record_detail,  name='medical_record_detail'),
    path('notifications/',                       v.patient_notifications,  name='notifications'),
]
