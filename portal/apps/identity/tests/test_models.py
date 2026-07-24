from django.test import TestCase

from apps.identity.models import User


class UserModelTests(TestCase):
    def test_display_name_is_preferred_string(self):
        user = User.objects.create_user(username="alpha", display_name="Alpha User")
        self.assertEqual(str(user), "Alpha User")
