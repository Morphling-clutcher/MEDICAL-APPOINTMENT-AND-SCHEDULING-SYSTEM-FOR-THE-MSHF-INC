from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from .models import Feedback
from .forms import FeedbackForm
from appointments.models import Appointment


@role_required('patient')
def feedback_list(request):
    feedbacks = Feedback.objects.filter(patient=request.user).select_related('appointment')
    completed_without_feedback = Appointment.objects.filter(
        patient=request.user, status='Completed'
    ).exclude(pk__in=feedbacks.filter(appointment__isnull=False).values('appointment_id'))
    return render(request, 'feedback/feedback_list.html', {
        'feedbacks': feedbacks,
        'to_review': completed_without_feedback,
    })


@role_required('patient')
def submit_feedback(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id, patient=request.user, status='Completed')
    existing = Feedback.objects.filter(patient=request.user, appointment=appointment).first()
    if existing:
        messages.info(request, 'You have already submitted feedback for this appointment.')
        return redirect('feedback:list')
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        fb = form.save(commit=False)
        fb.patient     = request.user
        fb.appointment = appointment
        fb.save()
        messages.success(request, 'Thank you for your feedback!')
        return redirect('feedback:list')
    return render(request, 'feedback/submit_feedback.html', {
        'form': form, 'appointment': appointment
    })
