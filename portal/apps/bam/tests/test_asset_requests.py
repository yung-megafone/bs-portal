from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.bam.models import (
    Asset,
    AssetRequest,
    AssetRequestEvent,
    AssetRequestItem,
    AssetStatus,
    AssetType,
)
from apps.bam.permissions import can_manage_asset_request, can_view_asset_request
from apps.bam.services import (
    allocate_request_item,
    create_asset_request,
    deny_asset_request_item,
    release_request_item,
    waitlist_position,
)
from apps.departments.models import Department, DepartmentMembership
from apps.identity.models import User
from apps.shit.models import Ticket
from apps.shit.services import create_ticket


class AssetRequestServiceTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(username="requester", password="test-password")
        self.manager = User.objects.create_user(username="manager", password="test-password")
        self.outsider = User.objects.create_user(username="outsider", password="test-password")
        self.sr69 = Department.objects.create(code="SR69", name="SubRosa69")
        self.dev5 = Department.objects.create(code="DEV5", name="Development")
        DepartmentMembership.objects.create(
            user=self.manager,
            department=self.sr69,
            role=DepartmentMembership.Role.MANAGER,
            is_active=True,
        )
        self.laptop_type = AssetType.objects.create(code="L", name="Laptop")
        self.radio_type = AssetType.objects.create(code="R", name="Radio")
        self.active = AssetStatus.objects.create(code="ACTIVE", name="Active", sort_order=10)
        self.repair = AssetStatus.objects.create(code="REPAIR", name="Repair", sort_order=40)
        self.pavilion = self._asset("BS-SR69-L-A001", "A001", self.laptop_type, model="Pavilion")
        self.thinkpad = self._asset("BS-SR69-L-A002", "A002", self.laptop_type, model="ThinkPad")
        self.today = date(2026, 9, 5)

    def _asset(self, asset_id, suffix, asset_type, model="", status=None, department=None):
        return Asset.objects.create(
            asset_id=asset_id,
            organization_code="BS",
            unique_hex=suffix,
            department=department or self.sr69,
            asset_type=asset_type,
            ownership=Asset.Ownership.COMPANY,
            model=model,
            status=status or self.active,
            created_by=self.manager,
        )

    def _request(self, *, mode=AssetRequestItem.PreferenceMode.ANY, preferred=None, start=None, end=None):
        return create_asset_request(
            actor=self.requester,
            purpose="RF capture work",
            requested_start=start or self.today,
            requested_end=end or (self.today + timedelta(days=2)),
            department=self.sr69,
            asset_type=self.laptop_type,
            preference_mode=mode,
            preferred_asset=preferred,
            justification="Need a development laptop.",
        )

    def test_request_number_and_initial_item_are_created(self):
        asset_request, item = self._request()
        self.assertRegex(asset_request.request_number, r"^BAMR-\d{2}-[0-9A-F]{6}$")
        self.assertEqual(item.status, AssetRequestItem.Status.PENDING)
        self.assertEqual(item.preference_mode, AssetRequestItem.PreferenceMode.ANY)
        self.assertTrue(asset_request.events.filter(event_type=AssetRequestEvent.EventType.CREATED).exists())

    def test_prefer_mode_uses_preferred_asset_when_available(self):
        asset_request, item = self._request(mode=AssetRequestItem.PreferenceMode.PREFER, preferred=self.pavilion)
        result = allocate_request_item(item=item, actor=self.manager)
        self.assertEqual(result.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(result.allocated_asset, self.pavilion)
        asset_request.refresh_from_db()
        self.assertEqual(asset_request.status, AssetRequest.Status.RESERVED)

    def test_prefer_mode_falls_back_to_equivalent_asset(self):
        # Occupy the Pavilion for the requested dates.
        first_request, first_item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        allocate_request_item(item=first_item, actor=self.manager)

        second_request, second_item = self._request(mode=AssetRequestItem.PreferenceMode.PREFER, preferred=self.pavilion)
        result = allocate_request_item(item=second_item, actor=self.manager)

        self.assertEqual(result.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(result.allocated_asset, self.thinkpad)
        second_request.refresh_from_db()
        self.assertEqual(second_request.status, AssetRequest.Status.RESERVED)

    def test_require_mode_waitlists_for_specific_unavailable_asset(self):
        first_request, first_item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        allocate_request_item(item=first_item, actor=self.manager)

        second_request, second_item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        result = allocate_request_item(item=second_item, actor=self.manager)

        self.assertEqual(result.status, AssetRequestItem.Status.WAITLISTED)
        self.assertIsNone(result.allocated_asset)
        self.assertEqual(waitlist_position(result), 1)
        second_request.refresh_from_db()
        self.assertEqual(second_request.status, AssetRequest.Status.QUEUED)

    def test_any_mode_uses_an_available_asset_without_changing_custody(self):
        asset_request, item = self._request()
        original_custodian = self.pavilion.current_custodian
        result = allocate_request_item(item=item, actor=self.manager)

        self.assertEqual(result.status, AssetRequestItem.Status.ALLOCATED)
        self.assertIn(result.allocated_asset, [self.pavilion, self.thinkpad])
        result.allocated_asset.refresh_from_db()
        self.assertEqual(result.allocated_asset.current_custodian, original_custodian)
        self.assertEqual(result.allocated_asset.status, self.active)

    def test_exact_requirement_cannot_be_manually_substituted(self):
        asset_request, item = self._request(
            mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred=self.pavilion,
        )
        with self.assertRaises(ValidationError):
            allocate_request_item(item=item, actor=self.manager, selected_asset=self.thinkpad)

    def test_overlapping_reservations_cannot_double_allocate_same_asset(self):
        first_request, first_item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        allocate_request_item(item=first_item, actor=self.manager)

        second_request, second_item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        with self.assertRaises(ValidationError):
            allocate_request_item(item=second_item, actor=self.manager, selected_asset=self.pavilion)

    def test_non_overlapping_reservations_can_reuse_same_asset(self):
        first_request, first_item = self._request(
            mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred=self.pavilion,
            start=self.today,
            end=self.today + timedelta(days=1),
        )
        allocate_request_item(item=first_item, actor=self.manager)

        second_request, second_item = self._request(
            mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred=self.pavilion,
            start=self.today + timedelta(days=2),
            end=self.today + timedelta(days=3),
        )
        result = allocate_request_item(item=second_item, actor=self.manager)
        self.assertEqual(result.allocated_asset, self.pavilion)

    def test_waitlist_position_only_counts_overlapping_windows(self):
        self.pavilion.status = self.repair
        self.pavilion.save(update_fields=["status"])

        earlier_request, earlier_item = self._request(
            mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred=self.pavilion,
            start=self.today + timedelta(days=30),
            end=self.today + timedelta(days=31),
        )
        allocate_request_item(item=earlier_item, actor=self.manager)

        current_request, current_item = self._request(
            mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred=self.pavilion,
            start=self.today,
            end=self.today + timedelta(days=2),
        )
        current_item = allocate_request_item(item=current_item, actor=self.manager)

        self.assertEqual(current_item.status, AssetRequestItem.Status.WAITLISTED)
        self.assertEqual(waitlist_position(current_item), 1)

    def test_repair_asset_is_not_allocated_but_can_be_waitlisted_exactly(self):
        self.pavilion.status = self.repair
        self.pavilion.save(update_fields=["status"])
        asset_request, item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        result = allocate_request_item(item=item, actor=self.manager)
        self.assertEqual(result.status, AssetRequestItem.Status.WAITLISTED)

    def test_release_does_not_change_custody_and_completes_request_when_done(self):
        asset_request, item = self._request(mode=AssetRequestItem.PreferenceMode.REQUIRE, preferred=self.pavilion)
        allocated = allocate_request_item(item=item, actor=self.manager)
        release_request_item(item=allocated, actor=self.manager, reason="Window ended")
        asset_request.refresh_from_db()
        self.pavilion.refresh_from_db()
        self.assertEqual(asset_request.status, AssetRequest.Status.COMPLETED)
        self.assertIsNone(self.pavilion.current_custodian)
        self.assertEqual(self.pavilion.status, self.active)

    def test_denial_requires_a_reason(self):
        asset_request, item = self._request()
        with self.assertRaises(ValidationError):
            deny_asset_request_item(item=item, actor=self.manager, reason="")
        deny_asset_request_item(item=item, actor=self.manager, reason="No suitable equipment can be issued.")
        item.refresh_from_db()
        asset_request.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.DENIED)
        self.assertEqual(asset_request.status, AssetRequest.Status.DENIED)

    def test_manager_permission_is_department_scoped(self):
        asset_request, item = self._request()
        self.assertTrue(can_view_asset_request(self.manager, asset_request))
        self.assertTrue(can_manage_asset_request(self.manager, asset_request))
        self.assertFalse(can_view_asset_request(self.outsider, asset_request))
        self.assertFalse(can_manage_asset_request(self.outsider, asset_request))

    def test_whole_request_management_requires_all_departments(self):
        asset_request, item = self._request()
        dev_asset = self._asset(
            "BS-DEV5-L-B001", "B001", self.laptop_type,
            department=self.dev5,
        )
        AssetRequestItem.objects.create(
            request=asset_request,
            department=self.dev5,
            asset_type=self.laptop_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=dev_asset,
        )
        self.assertTrue(can_view_asset_request(self.manager, asset_request))
        self.assertFalse(can_manage_asset_request(self.manager, asset_request))


class AssetRequestViewTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(username="requester", password="test-password")
        self.manager = User.objects.create_user(username="manager", password="test-password")
        self.outsider = User.objects.create_user(username="outsider", password="test-password")
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
        self.ticket = create_ticket(
            actor=self.requester,
            title="Capture corpus",
            description="Establish RF corpus.",
            ticket_type=Ticket.Type.REQUEST,
            severity=Ticket.Severity.SEV4,
            assigned_department=self.department,
        )

    def test_asset_detail_has_request_this_asset_link(self):
        self.client.force_login(self.requester)
        response = self.client.get(reverse("bam:detail", args=[self.asset.asset_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request this asset")
        self.assertContains(response, reverse("bam:request_asset", args=[self.asset.asset_id]))

    def test_request_asset_form_prefills_asset_and_can_reference_visible_ticket(self):
        self.client.force_login(self.requester)
        response = self.client.get(
            reverse("bam:request_asset", args=[self.asset.asset_id]),
            {"ticket": self.ticket.ticket_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.asset_id)
        self.assertContains(response, self.ticket.ticket_number)
        self.assertContains(response, "Prefer this asset; allow equivalent")
        self.assertContains(response, "Require this exact asset")

    def test_requester_can_submit_asset_request_without_creating_shit_ticket(self):
        self.client.force_login(self.requester)
        ticket_count = Ticket.objects.count()
        response = self.client.post(
            reverse("bam:request_asset", args=[self.asset.asset_id]),
            {
                "purpose": "RF capture session",
                "related_ticket": str(self.ticket.pk),
                "priority": AssetRequest.Priority.NORMAL,
                "requested_start": "2026-09-10",
                "requested_end": "2026-09-12",
                "desired_completion_date": "2026-09-13",
                "justification": "Need a controlled receiver.",
                "department": str(self.department.pk),
                "asset_type": str(self.asset_type.pk),
                "preference_mode": AssetRequestItem.PreferenceMode.REQUIRE,
                "preferred_asset": str(self.asset.pk),
                "item_note": "Exact receiver preferred for repeatability.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Ticket.objects.count(), ticket_count)
        asset_request = AssetRequest.objects.get(requester=self.requester)
        self.assertEqual(asset_request.related_ticket, self.ticket)
        self.assertEqual(asset_request.items.get().preferred_asset, self.asset)

    def test_related_request_is_backlinked_from_visible_shit_ticket(self):
        asset_request, item = create_asset_request(
            actor=self.requester,
            purpose="RF capture equipment",
            requested_start=date(2026, 9, 10),
            requested_end=date(2026, 9, 12),
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
            related_ticket=self.ticket,
        )
        self.client.force_login(self.requester)
        response = self.client.get(reverse("shit:detail", args=[self.ticket.ticket_number]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, asset_request.request_number)
        self.assertContains(response, reverse("bam:request_detail", args=[asset_request.request_number]))

    def test_outsider_cannot_view_another_users_request(self):
        asset_request, item = create_asset_request(
            actor=self.requester,
            purpose="Private request",
            requested_start=date(2026, 9, 10),
            requested_end=date(2026, 9, 12),
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
        )
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("bam:request_detail", args=[asset_request.request_number]))
        self.assertEqual(response.status_code, 403)

    def test_department_manager_can_allocate_but_requester_cannot(self):
        asset_request, item = create_asset_request(
            actor=self.requester,
            purpose="Manager approval",
            requested_start=date(2026, 9, 10),
            requested_end=date(2026, 9, 12),
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
        )

        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("bam:request_item_allocate", args=[asset_request.request_number, item.pk]),
            {"allocated_asset": str(self.asset.pk)},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("bam:request_item_allocate", args=[asset_request.request_number, item.pk]),
            {"allocated_asset": str(self.asset.pk)},
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(item.allocated_asset, self.asset)
