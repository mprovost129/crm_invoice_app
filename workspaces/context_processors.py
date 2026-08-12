def tenant_context(request):
    return {
        "ACTIVE_MEMBERSHIP": getattr(request, "membership", None),
        "ACTIVE_WORKSPACE": getattr(request, "workspace", None),
        "ACTIVE_BUSINESS": getattr(request, "business", None),
    }
