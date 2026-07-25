from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("departments", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="departmentmembership",
            name="one_active_membership_per_user_department",
        ),
        migrations.AddConstraint(
            model_name="departmentmembership",
            constraint=models.UniqueConstraint(
                fields=("user", "department"),
                name="unique_membership_per_user_department",
            ),
        ),
    ]
