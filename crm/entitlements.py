def enforce_contact_creation_allowed(*, business):
    """Stable hook for configurable plan limits introduced in the billing phase.

    Phase 2 has no Plan or Subscription model, so active contacts are intentionally
    unlimited. Contact creation still calls this hook so future backend entitlement
    enforcement cannot be bypassed by web, API, admin service actions, or jobs.
    """
    return None
