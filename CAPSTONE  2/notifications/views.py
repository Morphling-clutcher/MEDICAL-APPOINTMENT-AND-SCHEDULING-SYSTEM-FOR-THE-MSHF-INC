from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Notification


ROLE_TEMPLATES = {
    'patient': 'notifications/notification_list_patient.html',
    'doctor': 'notifications/notification_list_doctor.html',
    'secretary': 'notifications/notification_list_secretary.html',
    'admin': 'notifications/notification_list_admin.html',
}

# Bell-icon panel only previews the most recent notifications; the rest are
# reachable via the "See more" link, which routes to the full /notifications/ page.
PANEL_PREVIEW_LIMIT = 8


@login_required(login_url='/accounts/login/')
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    # Bell icon opens this as a modal (htmx request); the sidebar/menu link
    # is a normal navigation and still gets the full page below.
    if getattr(request, 'htmx', False):
        return render(request, 'notifications/_notification_list_modal.html', {
            'notifications': notifications, 'title': 'Notifications',
        })
    template = ROLE_TEMPLATES.get(request.user.role, 'notifications/notification_list_patient.html')
    return render(request, template, {
        'notifications': notifications
    })


def _grouped_notifications(user, limit=None):
    """Group the user's notifications into date buckets for the panel modal:
    Today / Yesterday / This Week / Earlier (empty groups are omitted).

    If `limit` is given, only the most recent `limit` notifications are
    bucketed (the queryset is already newest-first via model Meta.ordering),
    and the total unfiltered count is returned alongside the groups so the
    caller can decide whether to show a "See more" link."""
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.localtime()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = [
        {'label': 'Today', 'items': []},
        {'label': 'Yesterday', 'items': []},
        {'label': 'This Week', 'items': []},
        {'label': 'Earlier', 'items': []},
    ]
    qs = Notification.objects.filter(user=user)
    total_count = qs.count()
    if limit is not None:
        qs = qs[:limit]
    for notif in qs:
        d = timezone.localtime(notif.created_at).date()
        if d == today:
            groups[0]['items'].append(notif)
        elif d == yesterday:
            groups[1]['items'].append(notif)
        elif d > week_ago:
            groups[2]['items'].append(notif)
        else:
            groups[3]['items'].append(notif)
    return [g for g in groups if g['items']], total_count


@login_required(login_url='/accounts/login/')
def notification_panel(request):
    """Bell-icon notification panel — rendered into #modal-root via htmx."""
    groups, total_count = _grouped_notifications(request.user, limit=PANEL_PREVIEW_LIMIT)
    shown_count = sum(len(g['items']) for g in groups)
    return render(request, 'notifications/_notification_panel_modal.html', {
        'notification_groups': groups,
        'has_more': total_count > shown_count,
        'remaining_count': total_count - shown_count,
        'title': 'Notifications',
    })


@login_required(login_url='/accounts/login/')
def notification_detail(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    return render(request, 'notifications/_notification_detail_modal.html', {
        'notification': notif, 'title': 'Notification',
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
    # When triggered from inside the notification panel modal, stay in the
    # modal with the refreshed (all-read) grouped list instead of navigating.
    if getattr(request, 'htmx', False):
        groups, total_count = _grouped_notifications(request.user, limit=PANEL_PREVIEW_LIMIT)
        shown_count = sum(len(g['items']) for g in groups)
        return render(request, 'notifications/_notification_panel_modal.html', {
            'notification_groups': groups,
            'has_more': total_count > shown_count,
            'remaining_count': total_count - shown_count,
            'title': 'Notifications',
        })
    return redirect('notifications:list')
