import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_legacy_assets(apps, schema_editor):
    Ticket = apps.get_model("shit", "Ticket")
    TicketAssetLink = apps.get_model("shit", "TicketAssetLink")

    for ticket in Ticket.objects.exclude(related_asset_id__isnull=True).iterator():
        link, created = TicketAssetLink.objects.get_or_create(
            ticket_id=ticket.pk,
            asset_id=ticket.related_asset_id,
            defaults={
                "relationship_type": "RELATED",
                # The requester is the closest authoritative actor available in
                # the legacy Ticket row. No synthetic TicketEvent is created;
                # this migration preserves existing state rather than claiming
                # a new user action occurred at migration time.
                "created_by_id": ticket.requester_id,
                "note": "",
            },
        )
        if created:
            # auto_now_add/auto_now use migration time on insertion. The legacy
            # relationship existed with the ticket, so preserve the ticket's
            # timestamps as the best available historical approximation.
            TicketAssetLink.objects.filter(pk=link.pk).update(
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )


def noop_reverse(apps, schema_editor):
    # Do not copy multi-asset state back into the legacy single FK on rollback.
    # The legacy field itself remains present during this transition, so an
    # automatic lossy reverse mapping would be more dangerous than leaving it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("shit", "0003_ticket_queue_position"),
        ("bam", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticket",
            name="related_asset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="legacy_tickets",
                to="bam.asset",
            ),
        ),
        migrations.CreateModel(
            name="TicketAssetLink",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "relationship_type",
                    models.CharField(
                        choices=[
                            ("RELATED", "Related"),
                            ("AFFECTED", "Affected asset"),
                            ("REQUIRED", "Required for work"),
                            ("TEST_EQUIPMENT", "Test equipment"),
                            ("REPLACEMENT", "Replacement / alternate"),
                            ("SUPPORTING", "Supporting resource"),
                        ],
                        default="RELATED",
                        max_length=24,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ticket_links",
                        to="bam.asset",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ticket_asset_links_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="asset_links",
                        to="shit.ticket",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(
                        fields=["asset", "relationship_type"],
                        name="shit_tal_asset_rel_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("ticket", "asset"),
                        name="unique_ticket_asset_link",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="ticket",
            name="related_assets",
            field=models.ManyToManyField(
                blank=True,
                related_name="shit_tickets",
                through="shit.TicketAssetLink",
                to="bam.asset",
            ),
        ),
        migrations.RunPython(migrate_legacy_assets, noop_reverse),
        migrations.AlterField(
            model_name="ticketevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("COMMENTED", "Commented"),
                    ("INTERNAL_NOTE", "Internal note"),
                    ("ATTACHMENT_ADDED", "Attachment added"),
                    ("STATUS_CHANGED", "Status changed"),
                    ("SEVERITY_CHANGED", "Severity changed"),
                    ("DEPARTMENT_CHANGED", "Department changed"),
                    ("ASSIGNEE_CHANGED", "Assignee changed"),
                    ("ASSET_LINKED", "Asset linked"),
                    ("ASSET_UNLINKED", "Asset unlinked"),
                    (
                        "ASSET_RELATIONSHIP_CHANGED",
                        "Asset relationship changed",
                    ),
                    ("DOCUMENT_LINKED", "Document linked"),
                    ("QUEUE_REORDERED", "Queue reordered"),
                ],
                max_length=32,
            ),
        ),
    ]
