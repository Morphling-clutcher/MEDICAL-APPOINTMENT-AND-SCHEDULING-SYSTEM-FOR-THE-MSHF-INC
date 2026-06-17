from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    path('patient/<int:patient_id>/',  views.patient_records_view, name='patient_records'),
]
