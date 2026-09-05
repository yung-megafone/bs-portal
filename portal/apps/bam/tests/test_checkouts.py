from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bam.models import (
    Asset,
    AssetCheckout,
    AssetRequest,
    AssetRequestEvent,
    AssetRequestItem,
    AssetStatus,
    AssetType,
)
from apps.bam.services import (
    allocate_request_item,
    create_asset_request,
    handoff_checkout,
    issue_checkout,
    release_request_item,
    return_checkout,
)
from apps.departments.models import Department, DepartmentMembership
from apps.identity.models import User


class AssetCheckoutServiceTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(username="requester", password="pw")
        self.next_user = User.objects.create_user(username="next-user", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.outsider = User.objects.create_user(username="outsider", password="pw")
        self.department = Department.objects.create(code="SR69", name="SubRosa69")
        DepartmentMembership.objects.create(
            user=self.manager,
            department=self.department,
            role=DepartmentMembership.Role.MANAGER,
            is_active=True,
        )
        self.asset_type = AssetType.objects.create(code="L", name="Laptop")
        self.active = AssetStatus.objects.create(code="ACTIVE", name="Active", sort_order=10)
        self.asset = Asset.objects.create(
            asset_id="BS-SR69-L-6969",
            organization_code="BS",
            unique_hex="6969",
            department=self.department,
            asset_type=self.asset_type,
            ownership=Asset.Ownership.COMPANY,
            model="Pavilion",
            status=self.active,
            created_by=self.manager,
        )
        self.today = timezone.localdate()

    def _request(self, requester=None, start=None, end=None):
        return create_asset_request(
            actor=requester or self.requester,
            purpose="Development work",
            requested_start=start or self.today,
            requested_end=end or self.today,
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
        )

    def test_checkout_converts_reservation_into_physical_custody(self):
        asset_request, item = self._request()
        item = allocate_request_item(item=item, actor=self.manager)
        checkout = issue_checkout(item=item, actor=self.manager, notes="Issued with charger")

        item.refresh_from_db()
        asset_request.refresh_from_db()
        self.asset.refresh_from_db()

        self.assertEqual(item.status, AssetRequestItem.Status.CHECKED_OUT)
        self.assertEqual(asset_request.status, AssetRequest.Status.CHECKED_OUT)
        self.assertEqual(self.asset.current_custodian, self.requester)
        self.assertEqual(checkout.custodian, self.requester)
        self.assertIsNone(checkout.returned_at)
        self.assertTrue(
            asset_request.events.filter(event_type=AssetRequestEvent.EventType.CHECKED_OUT).exists()
        )

    def test_checkout_cannot_start_before_requested_window(self):
        asset_request, item = self._request(
            start=self.today + timedelta(days=2),
            end=self.today + timedelta(days=3),
        )
        item = allocate_request_item(item=item, actor=self.manager)
        with self.assertRaises(ValidationError):
            issue_checkout(item=item, actor=self.manager)

    def test_return_closes_custody_and_completes_request(self):
        asset_request, item = self._request()
        item = allocate_request_item(item=item, actor=self.manager)
        checkout = issue_checkout(item=item, actor=self.manager)

        returned, promoted = return_checkout(
            checkout=checkout,
            actor=self.manager,
            reason="Work complete",
        )

        item.refresh_from_db()
        asset_request.refresh_from_db()
        self.asset.refresh_from_db()
        returned.refresh_from_db()

        self.assertEqual(item.status, AssetRequestItem.Status.RETURNED)
        self.assertEqual(asset_request.status, AssetRequest.Status.COMPLETED)
        self.assertIsNone(self.asset.current_custodian)
        self.assertIsNotNone(returned.returned_at)
        self.assertEqual(promoted, [])

    def test_return_promotes_compatible_waitlist(self):
        first_request, first_item = self._request()
        first_item = allocate_request_item(item=first_item, actor=self.manager)
        checkout = issue_checkout(item=first_item, actor=self.manager)

        second_request, second_item = self._request(requester=self.next_user)
        second_item = allocate_request_item(item=second_item, actor=self.manager)
        self.assertEqual(second_item.status, AssetRequestItem.Status.WAITLISTED)

        _, promoted = return_checkout(checkout=checkout, actor=self.manager)

        second_item.refresh_from_db()
        self.assertEqual(second_item.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(second_item.allocated_asset, self.asset)
        self.assertEqual([row.pk for row in promoted], [second_item.pk])

    def test_releasing_unused_reservation_promotes_waitlist(self):
        first_request, first_item = self._request()
        first_item = allocate_request_item(item=first_item, actor=self.manager)

        second_request, second_item = self._request(requester=self.next_user)
        second_item = allocate_request_item(item=second_item, actor=self.manager)
        self.assertEqual(second_item.status, AssetRequestItem.Status.WAITLISTED)

        _, promoted = release_request_item(item=first_item, actor=self.manager, reason="No longer needed")

        second_item.refresh_from_db()
        self.assertEqual(second_item.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(second_item.allocated_asset, self.asset)
        self.assertEqual([row.pk for row in promoted], [second_item.pk])

    def test_direct_handoff_moves_custody_to_next_approved_user(self):
        # Current user has today's reservation.
        current_request, current_item = self._request(
            requester=self.requester,
            start=self.today,
            end=self.today,
        )
        current_item = allocate_request_item(item=current_item, actor=self.manager)
        current_checkout = issue_checkout(item=current_item, actor=self.manager)

        # Next user has a non-overlapping next-day reservation for the same asset.
        next_request, next_item = self._request(
            requester=self.next_user,
            start=self.today + timedelta(days=1),
            end=self.today + timedelta(days=1),
        )
        next_item = allocate_request_item(item=next_item, actor=self.manager)
        self.assertEqual(next_item.status, AssetRequestItem.Status.ALLOCATED)

        next_checkout = handoff_checkout(
            checkout=current_checkout,
            next_item=next_item,
            actor=self.manager,
            reason="Direct transfer at shift handoff",
        )

        current_item.refresh_from_db()
        next_item.refresh_from_db()
        current_checkout.refresh_from_db()
        self.asset.refresh_from_db()

        self.assertEqual(current_item.status, AssetRequestItem.Status.RETURNED)
        self.assertEqual(next_item.status, AssetRequestItem.Status.CHECKED_OUT)
        self.assertIsNotNone(current_checkout.returned_at)
        self.assertEqual(current_checkout.handoff_to, next_checkout)
        self.assertEqual(self.asset.current_custodian, self.next_user)
        self.assertEqual(next_checkout.custodian, self.next_user)

    def test_overdue_checkout_blocks_future_reservations_until_returned(self):
        old_request, old_item = self._request(
            requester=self.requester,
            start=self.today - timedelta(days=2),
            end=self.today - timedelta(days=1),
        )
        old_item.status = AssetRequestItem.Status.CHECKED_OUT
        old_item.allocated_asset = self.asset
        old_item.allocated_by = self.manager
        old_item.allocated_at = timezone.now() - timedelta(days=2)
        old_item.save()
        AssetCheckout.objects.create(
            request_item=old_item,
            asset=self.asset,
            custodian=self.requester,
            issued_by=self.manager,
        )

        new_request, new_item = self._request(requester=self.next_user)
        result = allocate_request_item(item=new_item, actor=self.manager)
        self.assertEqual(result.status, AssetRequestItem.Status.WAITLISTED)
        self.assertIsNone(result.allocated_asset)

    def test_overdue_property_uses_request_end_date(self):
        asset_request, item = self._request(
            start=self.today - timedelta(days=2),
            end=self.today - timedelta(days=1),
        )
        # Create the historical active checkout directly to test overdue display
        # semantics without bypassing issue_checkout's date-window guard.
        item.status = AssetRequestItem.Status.CHECKED_OUT
        item.allocated_asset = self.asset
        item.allocated_by = self.manager
        item.allocated_at = timezone.now() - timedelta(days=2)
        item.save()
        checkout = AssetCheckout.objects.create(
            request_item=item,
            asset=self.asset,
            custodian=self.requester,
            issued_by=self.manager,
        )
        self.assertTrue(checkout.is_overdue)
        self.assertEqual(checkout.overdue_days, 1)


class AssetCheckoutViewTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(username="requester", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.outsider = User.objects.create_user(username="outsider", password="pw")
        self.department = Department.objects.create(code="SR69", name="SubRosa69")
        DepartmentMembership.objects.create(
            user=self.manager,
            department=self.department,
            role=DepartmentMembership.Role.MANAGER,
            is_active=True,
        )
        self.asset_type = AssetType.objects.create(code="R", name="Radio")
        self.active = AssetStatus.objects.create(code="ACTIVE", name="Active", sort_order=10)
        self.asset = Asset.objects.create(
            asset_id="BS-SR69-R-6969",
            organization_code="BS",
            unique_hex="6969",
            department=self.department,
            asset_type=self.asset_type,
            ownership=Asset.Ownership.COMPANY,
            status=self.active,
            created_by=self.manager,
        )
        self.asset_request, self.item = create_asset_request(
            actor=self.requester,
            purpose="Radio test",
            requested_start=timezone.localdate(),
            requested_end=timezone.localdate(),
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
        )
        self.item = allocate_request_item(item=self.item, actor=self.manager)

    def test_requester_cannot_issue_own_checkout(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("bam:request_item_checkout", args=[self.asset_request.request_number, self.item.pk]),
            {"reason": "self issue"},
        )
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, AssetRequestItem.Status.ALLOCATED)

    def test_manager_can_issue_checkout_and_checkout_list_shows_it(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("bam:request_item_checkout", args=[self.asset_request.request_number, self.item.pk]),
            {"reason": "Issued at desk"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse("bam:checkout_list"), {"scope": "managed"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.asset_id)
        self.assertContains(response, self.asset_request.request_number)
        self.assertContains(response, "In custody")
    def test_asset_detail_hides_restricted_checkout_request_details(self):
        checkout = issue_checkout(item=self.item, actor=self.manager)

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("bam:detail", args=[self.asset.asset_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "currently checked out")
        self.assertContains(response, "details are restricted")
        self.assertNotContains(response, self.asset_request.request_number)

