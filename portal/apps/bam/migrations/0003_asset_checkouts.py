# Generated for B.S. Portal Chunk 4 — reservation-backed checkout/custody workflow.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bam", "0002_asset_requests"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assetevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("REGISTERED", "Registered"),
                    ("UPDATED", "Updated"),
                    ("STATUS_CHANGED", "Status changed"),
                    ("CUSTODY_ASSIGNED", "Custody assigned"),
                    ("CUSTODY_RETURNED", "Custody returned"),
                    ("EVIDENCE_ADDED", "Evidence added"),
                    ("RESERVATION_ALLOCATED", "Reservation allocated"),
                    ("RESERVATION_RELEASED", "Reservation released"),
                    ("CHECKOUT_ISSUED", "Checkout issued"),
                    ("CHECKOUT_RETURNED", "Checkout returned"),
                    ("CHECKOUT_HANDOFF", "Checkout handed off"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="assetrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("SUBMITTED", "Submitted"),
                    ("QUEUED", "Queued"),
                    ("PARTIALLY_RESERVED", "Partially reserved"),
                    ("RESERVED", "Reserved"),
                    ("PARTIALLY_CHECKED_OUT", "Partially checked out"),
                    ("CHECKED_OUT", "Checked out"),
                    ("DENIED", "Denied"),
                    ("CANCELLED", "Cancelled"),
                    ("COMPLETED", "Completed"),
                ],
                default="SUBMITTED",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="assetrequestitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending review"),
                    ("WAITLISTED", "Waitlisted"),
                    ("ALLOCATED", "Reserved"),
                    ("CHECKED_OUT", "Checked out"),
                    ("RETURNED", "Returned"),
                    ("RELEASED", "Released"),
                    ("DENIED", "Denied"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=16,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="assetrequestitem",
            name="bam_reqitem_allocated_has_asset",
        ),
        migrations.AddConstraint(
            model_name="assetrequestitem",
            constraint=models.CheckConstraint(
                condition=~models.Q(status__in=["ALLOCATED", "CHECKED_OUT", "RETURNED", "RELEASED"])
                | models.Q(allocated_asset__isnull=False),
                name="bam_reqitem_allocated_has_asset",
            ),
        ),
        migrations.AlterField(
            model_name="assetrequestevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("ITEM_ADDED", "Requirement added"),
                    ("WAITLISTED", "Waitlisted"),
                    ("ALLOCATED", "Reserved"),
                    ("PROMOTED", "Queue promoted"),
                    ("CHECKED_OUT", "Checked out"),
                    ("RETURNED", "Returned"),
                    ("HANDOFF", "Direct handoff"),
                    ("RELEASED", "Reservation released"),
                    ("DENIED", "Denied"),
                    ("CANCELLED", "Cancelled"),
                    ("COMPLETED", "Completed"),
                ],
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="AssetCheckout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("checked_out_at", models.DateTimeField(auto_now_add=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("return_reason", models.CharField(blank=True, max_length=240)),
                ("notes", models.CharField(blank=True, max_length=240)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkouts", to="bam.asset")),
                ("custodian", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bam_checkouts", to=settings.AUTH_USER_MODEL)),
                ("issued_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bam_checkouts_issued", to=settings.AUTH_USER_MODEL)),
                ("request_item", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="checkout", to="bam.assetrequestitem")),
                ("returned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bam_checkouts_returned", to=settings.AUTH_USER_MODEL)),
                ("handoff_to", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="handoff_from", to="bam.assetcheckout")),
            ],
            options={
                "ordering": ["-checked_out_at"],
                "indexes": [
                    models.Index(fields=["asset", "returned_at"], name="bam_checkout_asset_open_idx"),
                    models.Index(fields=["custodian", "returned_at"], name="bam_checkout_cust_open_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(returned_at__isnull=True) | models.Q(returned_at__gte=models.F("checked_out_at")),
                        name="bam_checkout_return_after_issue",
                    ),
                ],
            },
        ),
    ]
