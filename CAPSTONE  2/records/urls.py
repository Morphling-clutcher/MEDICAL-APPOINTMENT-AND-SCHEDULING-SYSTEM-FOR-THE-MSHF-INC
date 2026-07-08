from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    path('',                                   views.records_redirect,        name='records_redirect'),
    path('patient/<int:patient_id>/',          views.patient_records_view,    name='patient_records'),
    path('prescription/<int:pk>/attachment/',  views.prescription_attachment, name='prescription_attachment'),
]
