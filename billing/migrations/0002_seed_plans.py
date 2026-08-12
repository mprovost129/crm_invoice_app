from django.db import migrations


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")
    Workspace = apps.get_model("workspaces", "Workspace")

    free, _ = Plan.objects.update_or_create(
        code="free",
        defaults={
            "name": "Free",
            "description": "Core invoicing for a small service business.",
            "display_order": 10,
            "active_contact_limit": 25,
            "monthly_estimate_limit": 10,
            "monthly_invoice_limit": 10,
            "allow_online_payments": False,
            "allow_custom_branding": False,
            "allow_reminders": False,
            "allow_reporting": False,
            "allow_exports": False,
        },
    )
    Plan.objects.update_or_create(
        code="starter",
        defaults={
            "name": "Starter",
            "description": "Online payments, reminders, reports, exports, and higher limits.",
            "display_order": 20,
            "active_contact_limit": 1000,
            "monthly_estimate_limit": 1000,
            "monthly_invoice_limit": 1000,
            "allow_online_payments": True,
            "allow_custom_branding": True,
            "allow_reminders": True,
            "allow_reporting": True,
            "allow_exports": True,
        },
    )
    for workspace_id in Workspace.objects.values_list("pk", flat=True).iterator():
        Subscription.objects.get_or_create(
            workspace_id=workspace_id,
            defaults={
                "plan": free,
                "status": "active",
                "billing_interval": "none",
            },
        )


def remove_seeded_plans(apps, schema_editor):
    Subscription = apps.get_model("billing", "Subscription")
    Plan = apps.get_model("billing", "Plan")
    seeded = Plan.objects.filter(code__in=("free", "starter"))
    Subscription.objects.filter(plan__in=seeded).delete()
    seeded.delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed_plans, remove_seeded_plans)]
