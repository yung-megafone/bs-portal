# Generated for B.S. Portal Chunk 5 — BAM automation, stock custody, and self-service release.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def seed_vanguard_stock_custody(apps, schema_editor):
    User = apps.get_model("identity", "User")
    Asset = apps.get_model("bam", "Asset")
    AssetCustody = apps.get_model("bam", "AssetCustody")
    AssetEvent = apps.get_model("bam", "AssetEvent")
    Automation = apps.get_model("bam", "BAMAutomationSettings")

    vanguard = User.objects.filter(username__iexact="vanguard", is_active=True).first()
    defaults = {}
    if vanguard is not None:
        defaults = {
            "default_custodian_id": vanguard.pk,
            "automation_actor_id": vanguard.pk,
        }
    Automation.objects.get_or_create(id=1, defaults=defaults)

    if vanguard is None:
        return

    now = timezone.now()
    assets = Asset.objects.filter(
        ownership="COMPANY",
        current_custodian__isnull=True,
        status__is_terminal=False,
    )
    for asset in assets.iterator():
        Asset.objects.filter(pk=asset.pk).update(current_custodian_id=vanguard.pk)
        AssetCustody.objects.create(
            asset_id=asset.pk,
            custodian_id=vanguard.pk,
            assigned_at=now,
            assigned_by_id=vanguard.pk,
            reason="Chunk 5 default stock custody migration",
        )
        AssetEvent.objects.create(
            asset_id=asset.pk,
            event_type="CUSTODY_ASSIGNED",
            actor_id=vanguard.pk,
            summary="Custody assigned to Vanguard as default BAM stock custodian.",
            metadata={"automated": True, "migration": "0004_bam_automation"},
        )


def reverse_seed(apps, schema_editor):
    # Intentionally preserve custody/history if the schema is rolled back. A
    # rollback should not rewrite operational custody state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("bam", "0003_asset_checkouts"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="automatic_allocation_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Allow BAM automation to reserve/issue this asset when policy permits.",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="allocation_hold",
            field=models.BooleanField(
                default=False,
                help_text="Temporarily exclude this asset from automatic allocation.",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="allocation_hold_reason",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="assetcheckout",
            name="return_condition",
            field=models.CharField(
                choices=[
                    ("GOOD", "Good / ready for next user"),
                    ("MINOR_ISSUE", "Minor issue"),
                    ("DAMAGED", "Damaged"),
                    ("MISSING_ACCESSORY", "Missing accessory"),
                    ("NEEDS_ATTENTION", "Needs attention"),
                ],
                default="GOOD",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="assetcheckout",
            name="return_notes",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.CreateModel(
            name="BAMAutomationSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("auto_approve_available_requests", models.BooleanField(default=True)),
                ("auto_transfer_on_approval", models.BooleanField(default=True, help_text="Immediately issue custody when an automatically approved reservation is active today.")),
                ("auto_promote_waitlist", models.BooleanField(default=True)),
                ("auto_transfer_on_release", models.BooleanField(default=True, help_text="After a good-condition release, issue an active promoted/approved reservation automatically.")),
                ("allow_equivalent_substitution", models.BooleanField(default=True, help_text="For 'prefer' requests, automation may choose another eligible equivalent when the preferred asset is busy.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("automation_actor", models.ForeignKey(blank=True, help_text="Audit actor for automatic BAM actions. Defaults to the stock custodian when unset.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bam_automation_actor_settings", to=settings.AUTH_USER_MODEL)),
                ("default_custodian", models.ForeignKey(blank=True, help_text="Stock/default custodian used when an asset is not issued to a requester.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bam_default_custodian_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "BAM automation settings",
                "verbose_name_plural": "BAM automation settings",
            },
        ),
        migrations.RunPython(seed_vanguard_stock_custody, reverse_seed),
    ]
