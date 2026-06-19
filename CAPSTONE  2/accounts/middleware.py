class NoCacheMiddleware:
    """Forces the browser to revalidate with the server instead of serving a
    page from disk/back-forward cache, so the Back button after logout hits
    role_required/RoleRequiredMixin again rather than showing a stale page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/static/') and not request.path.startswith('/media/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
