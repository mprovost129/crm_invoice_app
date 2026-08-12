from .selectors import active_business_for_user, active_membership_for_user


class TenantContextMiddleware:
    """Attach only membership-verified workspace and business context to requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.workspace = None
        request.business = None

        if request.user.is_authenticated:
            request.membership = active_membership_for_user(request.user)
            if request.membership:
                request.workspace = request.membership.workspace
                request.business = active_business_for_user(
                    request.user,
                    workspace=request.workspace,
                )

        return self.get_response(request)
