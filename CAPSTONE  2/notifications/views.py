from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from .models import Notification


ROLE_TEMPLATES = {
    'patient': 'notifications/notification_list_patient.html',
    'doctor': 'notifications/notification_list_doctor.html',
    'secretary': 'notifications/notification_list_secretary.html',
    'admin': 'notifications/notification_list_admin.html',
}


def _group_notifications(notifications):
    """Group notifications into today, yesterday, and older buckets."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    groups = []
    today_list, yesterday_list, older_list = [], [], []
    for notif in notifications:
        notif_date = timezone.localtime(notif.created_at).date()
        if notif_date == today:
            today_list.append(notif)
        elif notif_date == yesterday:
            yesterday_list.append(notif)
        else:
            older_list.append(notif)
    if today_list:
        groups.append({'label': 'Today', 'items': today_list})
    if yesterday_list:
        groups.append({'label': 'Yesterday', 'items': yesterday_list})
    if older_list:
        groups.append({'label': 'Earlier', 'items': older_list})
    return groups


@login_required(login_url='/accounts/login/')
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    template = ROLE_TEMPLATES.get(request.user.role, 'notifications/notification_list_patient.html')
    return render(request, template, {
        'notifications': notifications,
        'notification_groups': _group_notifications(notifications),
    })


@login_required(login_url='/accounts/login/')
def notification_panel(request):
    """HTMX endpoint — returns the notification slide-in panel fragment."""
    notifications = Notification.objects.filter(user=request.user)
    return render(request, 'notifications/_notification_panel_modal.html', {
        'notifications': notifications,
        'notification_groups': _group_notifications(notifications),
        'title': 'Notifications',
    })


@login_required(login_url='/accounts/login/')
def notification_detail(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    return render(request, 'notifications/_notification_detail_modal.html', {
        'notification': notif, 'title': 'Notification Detail',
    })


@login_required(login_url='/accounts/login/')
def mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    if request.htmx:
        response = render(request, 'notifications/_notification_detail_modal.html', {'notification': notif})
        response['HX-Redirect'] = '/notifications/'
        return response
    return redirect('notifications:list')


@login_required(login_url='/accounts/login/')
def notification_dismiss(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.delete()
    if request.htmx:
        response = HttpResponse(status=204)
        response['HX-Redirect'] = '/notifications/'
        return response
    return redirect('notifications:list')


@login_required(login_url='/accounts/login/')
def mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if request.htmx:
        notifications = Notification.objects.filter(user=request.user)
        return render(request, 'notifications/_notification_panel_modal.html', {
            'notifications': notifications,
            'notification_groups': _group_notifications(notifications),
            'title': 'Notifications',
        })
    return redirect('notifications:list')
