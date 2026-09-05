from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bam.models import (
    Asset,
    AssetCheckout,
    AssetRequestItem,
    AssetStatus,
    AssetType,
    BAMAutomationSettings,
)
from apps.bam.services import (
    allocate_request_item,
    create_asset,
    create_asset_request,
    issue_checkout,
    self_release_checkout,
    process_due_bam_automation,
    assign_custody,
)
from apps.departments.models import Department
from apps.identity.models import User


class BAMAutomationTests(TestCase):
    def setUp(self):
        self.vanguard = User.objects.create_user(username="vanguard", password="pw")
        self.requester = User.objects.create_user(username="oma", password="pw")
        self.next_user = User.objects.create_user(username="next-user", password="pw")
        self.admin = User.objects.create_user(username="admin", password="pw", is_staff=True)
        self.department = Department.objects.create(code="SR69", name="SubRosa69")
        self.asset_type = AssetType.objects.create(code="R", name="Radio")
        self.active = AssetStatus.objects.create(code="ACTIVE", name="Active", sort_order=10)
        self.settings = BAMAutomationSettings.objects.get(pk=1)
        self.settings.default_custodian = self.vanguard
        self.settings.automation_actor = self.vanguard
        self.settings.auto_approve_available_requests = True
        self.settings.auto_transfer_on_approval = True
        self.settings.auto_promote_waitlist = True
        self.settings.auto_transfer_on_release = True
        self.settings.allow_equivalent_substitution = True
        self.settings.save()
        self.today = timezone.localdate()

    def _asset(self, suffix="6969", custodian=None, automatic=True):
        return Asset.objects.create(
            asset_id=f"BS-SR69-R-{suffix}",
            organization_code="BS",
            unique_hex=suffix,
            department=self.department,
            asset_type=self.asset_type,
            ownership=Asset.Ownership.COMPANY,
            status=self.active,
            current_custodian=self.vanguard if custodian is None else custodian,
            automatic_allocation_enabled=automatic,
            created_by=self.admin,
        )

    def _request(self, requester, preferred, *, apply_automation=True, mode=AssetRequestItem.PreferenceMode.REQUIRE):
        return create_asset_request(
            actor=requester,
            purpose="Radio work",
            requested_start=self.today,
            requested_end=self.today,
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=mode,
            preferred_asset=preferred if mode != AssetRequestItem.PreferenceMode.ANY else None,
            apply_automation=apply_automation,
        )

    def test_new_company_asset_defaults_to_vanguard_stock_custody(self):
        asset = create_asset(
            actor=self.admin,
            department=self.department,
            asset_type=self.asset_type,
            status=self.active,
            ownership=Asset.Ownership.COMPANY,
            model="MD-UV390 Plus",
        )
        self.assertEqual(asset.current_custodian, self.vanguard)
        self.assertTrue(asset.custody_history.filter(custodian=self.vanguard, returned_at__isnull=True).exists())

    def test_available_request_auto_approves_and_transfers_custody(self):
        asset = self._asset()
        asset_request, item = self._request(self.requester, asset)
        item.refresh_from_db()
        asset.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.CHECKED_OUT)
        self.assertEqual(item.allocated_asset, asset)
        self.assertEqual(asset.current_custodian, self.requester)
        self.assertTrue(AssetCheckout.objects.filter(request_item=item, returned_at__isnull=True).exists())

    def test_unavailable_exact_asset_enters_queue(self):
        asset = self._asset()
        first_request, first_item = self._request(self.requester, asset, apply_automation=False)
        first_item = allocate_request_item(item=first_item, actor=self.admin)
        issue_checkout(item=first_item, actor=self.admin)

        second_request, second_item = self._request(self.next_user, asset)
        second_item.refresh_from_db()
        self.assertEqual(second_item.status, AssetRequestItem.Status.WAITLISTED)
        self.assertIsNone(second_item.allocated_asset)

    def test_automation_pulse_reconsiders_waitlisted_exact_asset_after_it_returns_to_stock(self):
        asset = self._asset(custodian=self.requester)
        asset_request, item = self._request(self.next_user, asset)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.WAITLISTED)

        assign_custody(
            asset=asset,
            custodian=self.vanguard,
            actor=self.admin,
            reason="Returned to stock",
        )
        counts = process_due_bam_automation(fallback_actor=self.vanguard)

        item.refresh_from_db()
        asset.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.CHECKED_OUT)
        self.assertEqual(item.allocated_asset, asset)
        self.assertEqual(asset.current_custodian, self.next_user)
        self.assertGreaterEqual(counts["promoted"], 1)
        self.assertGreaterEqual(counts["checked_out"], 1)

    def test_waitlisted_reconciliation_does_not_duplicate_waitlist_events(self):
        asset = self._asset(custodian=self.requester)
        asset_request, item = self._request(self.next_user, asset)
        original_count = asset_request.events.filter(event_type="WAITLISTED").count()
        process_due_bam_automation(fallback_actor=self.vanguard)
        process_due_bam_automation(fallback_actor=self.vanguard)
        self.assertEqual(
            asset_request.events.filter(event_type="WAITLISTED").count(),
            original_count,
        )

    def test_asset_can_opt_out_of_automatic_allocation_but_still_be_manually_selected(self):
        asset = self._asset(automatic=False)
        asset_request, item = self._request(self.requester, asset)
        item.refresh_from_db()
        self.assertEqual(item.status, AssetRequestItem.Status.WAITLISTED)

        manual = allocate_request_item(item=item, actor=self.admin, selected_asset=asset)
        self.assertEqual(manual.status, AssetRequestItem.Status.ALLOCATED)
        self.assertEqual(manual.allocated_asset, asset)

    def test_good_self_release_promotes_and_transfers_to_next_requester(self):
        asset = self._asset()
        current_request, current_item = self._request(self.requester, asset, apply_automation=False)
        current_item = allocate_request_item(item=current_item, actor=self.admin)
        checkout = issue_checkout(item=current_item, actor=self.admin)

        next_request, next_item = self._request(self.next_user, asset, apply_automation=False)
        next_item = allocate_request_item(item=next_item, actor=self.admin)
        self.assertEqual(next_item.status, AssetRequestItem.Status.WAITLISTED)

        returned, promoted, active_next = self_release_checkout(
            checkout=checkout,
            actor=self.requester,
            condition=AssetCheckout.ReturnCondition.GOOD,
        )
        asset.refresh_from_db()
        next_item.refresh_from_db()
        self.assertEqual(next_item.status, AssetRequestItem.Status.CHECKED_OUT)
        self.assertEqual(asset.current_custodian, self.next_user)
        self.assertIsNotNone(active_next)
        self.assertEqual(active_next.custodian, self.next_user)
        self.assertEqual([row.pk for row in promoted], [next_item.pk])

    def test_non_good_release_returns_to_vanguard_and_sets_hold(self):
        asset = self._asset()
        current_request, current_item = self._request(self.requester, asset, apply_automation=False)
        current_item = allocate_request_item(item=current_item, actor=self.admin)
        checkout = issue_checkout(item=current_item, actor=self.admin)

        next_request, next_item = self._request(self.next_user, asset, apply_automation=False)
        next_item = allocate_request_item(item=next_item, actor=self.admin)
        self.assertEqual(next_item.status, AssetRequestItem.Status.WAITLISTED)

        returned, promoted, active_next = self_release_checkout(
            checkout=checkout,
            actor=self.requester,
            condition=AssetCheckout.ReturnCondition.DAMAGED,
            notes="Antenna connector damaged",
        )
        asset.refresh_from_db()
        next_item.refresh_from_db()
        self.assertEqual(asset.current_custodian, self.vanguard)
        self.assertTrue(asset.allocation_hold)
        self.assertIn("Antenna", asset.allocation_hold_reason)
        self.assertEqual(next_item.status, AssetRequestItem.Status.WAITLISTED)
        self.assertEqual(promoted, [])
        self.assertIsNone(active_next)

    def test_disabling_auto_transfer_keeps_released_asset_with_vanguard(self):
        self.settings.auto_transfer_on_release = False
        self.settings.save(update_fields=["auto_transfer_on_release", "updated_at"])
        asset = self._asset()
        current_request, current_item = self._request(self.requester, asset, apply_automation=False)
        current_item = allocate_request_item(item=current_item, actor=self.admin)
        checkout = issue_checkout(item=current_item, actor=self.admin)

        next_request, next_item = self._request(self.next_user, asset, apply_automation=False)
        next_item = allocate_request_item(item=next_item, actor=self.admin)
        self.assertEqual(next_item.status, AssetRequestItem.Status.WAITLISTED)

        _, promoted, active_next = self_release_checkout(
            checkout=checkout,
            actor=self.requester,
            condition=AssetCheckout.ReturnCondition.GOOD,
        )
        asset.refresh_from_db()
        next_item.refresh_from_db()
        self.assertEqual(asset.current_custodian, self.vanguard)
        self.assertEqual(next_item.status, AssetRequestItem.Status.ALLOCATED)
        self.assertIsNone(active_next)
        self.assertEqual([row.pk for row in promoted], [next_item.pk])


class BAMAutomationViewTests(TestCase):
    def setUp(self):
        self.vanguard = User.objects.create_user(username="vanguard", password="pw")
        self.requester = User.objects.create_user(username="oma", password="pw")
        self.admin = User.objects.create_user(username="admin", password="pw", is_staff=True)
        self.department = Department.objects.create(code="SR69", name="SubRosa69")
        self.asset_type = AssetType.objects.create(code="R", name="Radio")
        self.active = AssetStatus.objects.create(code="ACTIVE", name="Active", sort_order=10)
        settings = BAMAutomationSettings.objects.get(pk=1)
        settings.default_custodian = self.vanguard
        settings.automation_actor = self.vanguard
        settings.save()
        self.asset = Asset.objects.create(
            asset_id="BS-SR69-R-6969",
            organization_code="BS",
            unique_hex="6969",
            department=self.department,
            asset_type=self.asset_type,
            ownership=Asset.Ownership.COMPANY,
            status=self.active,
            current_custodian=self.vanguard,
            created_by=self.admin,
        )
        self.today = timezone.localdate()

    def test_request_submit_renders_success_as_global_toast(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("bam:request_asset", args=[self.asset.asset_id]),
            {
                "purpose": "Radio test",
                "priority": "NORMAL",
                "requested_start": self.today.isoformat(),
                "requested_end": self.today.isoformat(),
                "desired_completion_date": "",
                "justification": "",
                "department": str(self.department.pk),
                "asset_type": str(self.asset_type.pk),
                "preference_mode": AssetRequestItem.PreferenceMode.REQUIRE,
                "preferred_asset": str(self.asset.pk),
                "item_note": "",
                "related_ticket": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-toast')
        self.assertContains(response, "approved automatically")

    def test_current_custodian_can_self_release_from_checkout_endpoint(self):
        request, item = create_asset_request(
            actor=self.requester,
            purpose="Radio test",
            requested_start=self.today,
            requested_end=self.today,
            department=self.department,
            asset_type=self.asset_type,
            preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
            preferred_asset=self.asset,
        )
        item = allocate_request_item(item=item, actor=self.admin)
        checkout = issue_checkout(item=item, actor=self.admin)
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("bam:checkout_self_release", args=[checkout.pk]),
            {"condition": AssetCheckout.ReturnCondition.GOOD, "notes": "", "next": reverse("bam:checkout_list")},
        )
        self.assertEqual(response.status_code, 302)
        checkout.refresh_from_db()
        self.assertIsNotNone(checkout.returned_at)
