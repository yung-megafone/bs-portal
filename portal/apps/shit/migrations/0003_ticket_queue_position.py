from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shit", "0002_remove_ticketsequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="queue_position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name="ticket",
            index=models.Index(
                fields=["status", "queue_position"],
                name="shit_tkt_status_queue_idx",
            ),
        ),
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
                    ("DOCUMENT_LINKED", "Document linked"),
                    ("QUEUE_REORDERED", "Queue reordered"),
                ],
                max_length=32,
            ),
        ),
    ]
