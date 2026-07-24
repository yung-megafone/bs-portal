import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Portal identity.

    A custom user model exists from migration zero so later identity/RBAC work does
    not require replacing Django's default User table in a live database.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.display_name or self.get_full_name() or self.username
