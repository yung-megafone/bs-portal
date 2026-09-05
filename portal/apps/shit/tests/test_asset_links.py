from django.test import TestCase
from django.urls import reverse

from apps.bam.models import Asset, AssetStatus, AssetType
from apps.departments.models import Department, DepartmentMembership
from apps.identity.models import User
from apps.shit.models import Ticket, TicketAssetLink, TicketEvent
from apps.shit.services import (
    add_ticket_asset_link,
    create_ticket,
    remove_ticket_asset_link,
    update_ticket,
    update_ticket_asset_link,
)


class TicketAssetLinkTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username="requester",
            password="test-password",
        )
        self.agent = User.objects.create_user(
            username="agent",
            password="test-password",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="test-password",
        )
        self.department = Department.objects.create(
            code="SR69",
            name="SubRosa69",
        )
        DepartmentMembership.objects.create(
            user=self.agent,
            department=self.department,
            is_active=True,
        )
        self.asset_type = AssetType.objects.create(code="R", name="Radio")
        self.asset_status = AssetStatus.objects.create(
            code="ACTIVE",
            name="Active",
            sort_order=10,
        )
        self.first_asset = self._asset("BS-SR69-R-1001", "1001")
        self.second_asset = self._asset("BS-SR69-R-1002", "1002")

    def _asset(self, asset_id, suffix):
        return Asset.objects.create(
            asset_id=asset_id,
            organization_code="BS",
            unique_hex=suffix,
            department=self.department,
            asset_type=self.asset_type,
            ownership=Asset.Ownership.COMPANY,
            status=self.asset_status,
            created_by=self.agent,
        )

    def _ticket(self, related_assets=None):
        return create_ticket(
            actor=self.requester,
            title="Multi-asset test",
            description="Test multiple BAM relationships.",
            ticket_type=Ticket.Type.REQUEST,
            severity=Ticket.Severity.SEV4,
            assigned_department=self.department,
            related_assets=related_assets or [],
            asset_relationship=TicketAssetLink.RelationshipType.REQUIRED,
        )

    def test_ticket_can_reference_multiple_assets(self):
        ticket = self._ticket([self.first_asset, self.second_asset])

        links = list(ticket.asset_links.order_by("asset__asset_id"))
        self.assertEqual(len(links), 2)
        self.assertEqual(
            {link.asset_id for link in links},
            {self.first_asset.pk, self.second_asset.pk},
        )
        self.assertTrue(
            all(
                link.relationship_type == TicketAssetLink.RelationshipType.REQUIRED
                for link in links
            )
        )
        self.assertEqual(
            ticket.events.filter(
                event_type=TicketEvent.EventType.ASSET_LINKED
            ).count(),
            2,
        )

    def test_new_ticket_does_not_write_legacy_single_asset_field(self):
        ticket = self._ticket([self.first_asset])

        ticket.refresh_from_db()
        self.assertIsNone(ticket.related_asset_id)
        self.assertTrue(ticket.asset_links.filter(asset=self.first_asset).exists())

    def test_legacy_create_service_argument_maps_to_new_relationship(self):
        ticket = create_ticket(
            actor=self.requester,
            title="Legacy caller",
            description="Compatibility path",
            ticket_type=Ticket.Type.REQUEST,
            severity=Ticket.Severity.SEV5,
            assigned_department=self.department,
            related_asset=self.first_asset,
        )

        self.assertIsNone(ticket.related_asset_id)
        self.assertTrue(ticket.asset_links.filter(asset=self.first_asset).exists())

    def test_same_asset_cannot_be_linked_twice(self):
        ticket = self._ticket([self.first_asset])

        with self.assertRaisesMessage(ValueError, "already linked"):
            add_ticket_asset_link(
                ticket=ticket,
                actor=self.agent,
                asset=self.first_asset,
                relationship_type=TicketAssetLink.RelationshipType.RELATED,
            )

        self.assertEqual(ticket.asset_links.count(), 1)

    def test_relationship_update_is_audited(self):
        ticket = self._ticket([self.first_asset])
        link = ticket.asset_links.get(asset=self.first_asset)

        update_ticket_asset_link(
            ticket=ticket,
            link=link,
            actor=self.agent,
            relationship_type=TicketAssetLink.RelationshipType.TEST_EQUIPMENT,
            note="Used for decoder validation.",
        )

        link.refresh_from_db()
        self.assertEqual(
            link.relationship_type,
            TicketAssetLink.RelationshipType.TEST_EQUIPMENT,
        )
        self.assertEqual(link.note, "Used for decoder validation.")
        self.assertTrue(
            ticket.events.filter(
                event_type=TicketEvent.EventType.ASSET_RELATIONSHIP_CHANGED,
                metadata__asset_id=self.first_asset.asset_id,
            ).exists()
        )

    def test_unlink_is_audited_without_changing_asset(self):
        ticket = self._ticket([self.first_asset])
        link = ticket.asset_links.get(asset=self.first_asset)
        asset_pk = self.first_asset.pk

        remove_ticket_asset_link(ticket=ticket, link=link, actor=self.agent)

        self.assertFalse(ticket.asset_links.filter(asset_id=asset_pk).exists())
        self.assertTrue(Asset.objects.filter(pk=asset_pk).exists())
        self.assertTrue(
            ticket.events.filter(
                event_type=TicketEvent.EventType.ASSET_UNLINKED,
                metadata__asset_id=self.first_asset.asset_id,
            ).exists()
        )

    def test_normal_ticket_update_does_not_change_asset_relationships(self):
        ticket = self._ticket([self.first_asset, self.second_asset])
        before = set(ticket.asset_links.values_list("asset_id", flat=True))

        update_ticket(
            ticket=ticket,
            actor=self.agent,
            status=Ticket.Status.IN_PROGRESS,
            severity=ticket.severity,
            assigned_department=ticket.assigned_department,
            assigned_user=self.agent,
            related_document="STD-7100",
        )

        after = set(ticket.asset_links.values_list("asset_id", flat=True))
        self.assertEqual(before, after)

    def test_manager_can_add_asset_from_detail_endpoint(self):
        ticket = self._ticket()
        self.client.force_login(self.agent)

        response = self.client.post(
            reverse("shit:asset_add", args=[ticket.ticket_number]),
            {
                "asset": str(self.first_asset.pk),
                "relationship_type": TicketAssetLink.RelationshipType.TEST_EQUIPMENT,
                "note": "Capture receiver",
            },
        )

        self.assertEqual(response.status_code, 302)
        link = ticket.asset_links.get(asset=self.first_asset)
        self.assertEqual(
            link.relationship_type,
            TicketAssetLink.RelationshipType.TEST_EQUIPMENT,
        )

    def test_requester_cannot_manage_asset_links_without_agent_permission(self):
        ticket = self._ticket()
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("shit:asset_add", args=[ticket.ticket_number]),
            {
                "asset": str(self.first_asset.pk),
                "relationship_type": TicketAssetLink.RelationshipType.RELATED,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ticket.asset_links.exists())

    def test_detail_renders_all_linked_assets_and_relationships(self):
        ticket = self._ticket([self.first_asset, self.second_asset])
        self.client.force_login(self.agent)

        response = self.client.get(
            reverse("shit:detail", args=[ticket.ticket_number])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_asset.asset_id)
        self.assertContains(response, self.second_asset.asset_id)
        self.assertContains(response, "Required for work", count=2)


    def test_bam_asset_detail_shows_only_visible_ticket_backlinks(self):
        ticket = self._ticket([self.first_asset])

        self.client.force_login(self.agent)
        visible = self.client.get(
            reverse("bam:detail", args=[self.first_asset.asset_id])
        )
        self.assertEqual(visible.status_code, 200)
        self.assertContains(visible, ticket.ticket_number)
        self.assertContains(visible, "Required for work")

        self.client.force_login(self.outsider)
        hidden = self.client.get(
            reverse("bam:detail", args=[self.first_asset.asset_id])
        )
        self.assertEqual(hidden.status_code, 200)
        self.assertNotContains(hidden, ticket.ticket_number)

    def test_ticket_search_matches_any_linked_asset(self):
        ticket = self._ticket([self.second_asset])
        self.client.force_login(self.agent)

        response = self.client.get(
            reverse("shit:list"),
            {"scope": "department", "view": "list", "q": self.second_asset.asset_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ticket.ticket_number)

    def test_create_view_accepts_multiple_asset_ids(self):
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("shit:create"),
            {
                "title": "Need several test assets",
                "description": "Laptop, SDR, and radio context belongs together.",
                "ticket_type": Ticket.Type.REQUEST,
                "severity": Ticket.Severity.SEV4,
                "assigned_department": str(self.department.pk),
                "related_assets": [
                    str(self.first_asset.pk),
                    str(self.second_asset.pk),
                ],
                "asset_relationship": TicketAssetLink.RelationshipType.REQUIRED,
                "related_document": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get(title="Need several test assets")
        self.assertEqual(ticket.asset_links.count(), 2)
