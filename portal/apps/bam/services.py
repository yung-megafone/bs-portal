from __future__ import annotations

import hashlib
import mimetypes
import re
import secrets
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Asset, AssetCheckout, AssetCustody, AssetEvent, AssetEvidence, BAMAutomationSettings

MAX_ID_ATTEMPTS = 65536
HEX_RE = re.compile(r"^[0-9A-F]{4}$")


def get_bam_automation_settings():
    settings_obj, _ = BAMAutomationSettings.objects.get_or_create(pk=1)
    return settings_obj


def get_bam_default_custodian():
    """Return the configured stock custodian, falling back to Vanguard by username."""
    settings_obj = get_bam_automation_settings()
    if settings_obj.default_custodian_id:
        return settings_obj.default_custodian
    user = get_user_model().objects.filter(username__iexact="vanguard", is_active=True).first()
    if user is not None:
        settings_obj.default_custodian = user
        if not settings_obj.automation_actor_id:
            settings_obj.automation_actor = user
            settings_obj.save(update_fields=["default_custodian", "automation_actor", "updated_at"])
        else:
            settings_obj.save(update_fields=["default_custodian", "updated_at"])
    return user


def get_bam_automation_actor(fallback):
    settings_obj = get_bam_automation_settings()
    return settings_obj.automation_actor or settings_obj.default_custodian or get_bam_default_custodian() or fallback


def _automatic_event_metadata(metadata=None):
    payload = dict(metadata or {})
    payload["automated"] = True
    return payload


def normalize_code(value, label="Code"):
    normalized = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]+", normalized):
        raise ValidationError(f"{label} may contain only uppercase letters and numbers.")
    return normalized


def normalize_preferred_suffix(value):
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        return None
    if not HEX_RE.fullmatch(normalized):
        raise ValidationError("Preferred suffix must be exactly four hexadecimal characters (0-9, A-F).")
    return normalized


def build_asset_id(organization_code, department_code, type_code, unique_hex):
    org = normalize_code(organization_code, "Organization code")
    department = normalize_code(department_code, "Department code")
    asset_type = normalize_code(type_code, "Asset type code")
    suffix = str(unique_hex).strip().upper()
    if not HEX_RE.fullmatch(suffix):
        raise ValidationError("Asset suffix must be exactly four hexadecimal characters.")
    return f"{org}-{department}-{asset_type}-{suffix}"


def _event(asset, actor, event_type, summary, metadata=None):
    return AssetEvent.objects.create(
        asset=asset,
        actor=actor,
        event_type=event_type,
        summary=summary,
        metadata=metadata or {},
    )


def _is_duplicate_key(exc):
    cause = getattr(exc, "__cause__", None)
    args = getattr(cause, "args", ()) or getattr(exc, "args", ())
    return bool(args and args[0] == 1062)


def create_asset(
    *, actor, department, asset_type, status, ownership, manufacturer="", model="",
    serial_number="", custodian=None, acquired_at=None, notes="", organization_code="BS",
    preferred_suffix=None,
):
    """Register an asset, honoring a preferred 4-hex suffix when it is available.

    The database unique constraints are authoritative. BAM attempts the preferred
    suffix first; a duplicate-key collision falls through to cryptographically
    random suffix generation. No namespace-wide pre-read is required.
    """
    organization_code = normalize_code(organization_code, "Organization code")
    if custodian is None and ownership == Asset.Ownership.COMPANY:
        custodian = get_bam_default_custodian()
    requested = normalize_preferred_suffix(preferred_suffix)
    candidates = [requested] if requested else []

    for _ in range(MAX_ID_ATTEMPTS):
        unique_hex = candidates.pop(0) if candidates else secrets.token_hex(2).upper()
        asset_id = build_asset_id(organization_code, department.code, asset_type.code, unique_hex)
        try:
            with transaction.atomic():
                asset = Asset.objects.create(
                    asset_id=asset_id,
                    organization_code=organization_code,
                    unique_hex=unique_hex,
                    department=department,
                    asset_type=asset_type,
                    ownership=ownership,
                    manufacturer=(manufacturer or "").strip(),
                    model=(model or "").strip(),
                    serial_number=(serial_number or "").strip(),
                    status=status,
                    current_custodian=custodian,
                    acquired_at=acquired_at,
                    retired_at=date.today() if status.is_terminal else None,
                    notes=(notes or "").strip(),
                    created_by=actor,
                )
                metadata = {"assigned_suffix": unique_hex}
                if requested:
                    metadata.update({
                        "preferred_suffix": requested,
                        "preferred_suffix_used": unique_hex == requested,
                    })
                _event(asset, actor, AssetEvent.EventType.REGISTERED, f"Asset registered as {asset.asset_id}.", metadata)
                if custodian:
                    AssetCustody.objects.create(
                        asset=asset,
                        custodian=custodian,
                        assigned_at=timezone.now(),
                        assigned_by=actor,
                        reason="Initial custody assignment",
                    )
                    _event(asset, actor, AssetEvent.EventType.CUSTODY_ASSIGNED, f"Custody assigned to {custodian}.")
                return asset
        except IntegrityError as exc:
            if _is_duplicate_key(exc):
                # Preferred collision or an extremely rare random collision: retry.
                continue
            raise

    raise RuntimeError("Unable to allocate a unique asset suffix after repeated attempts.")


def change_asset_status(*, asset, new_status, actor, reason=""):
    old_status = asset.status
    with transaction.atomic():
        asset.status = new_status
        asset.retired_at = date.today() if new_status.is_terminal else None
        asset.save(update_fields=["status", "retired_at", "updated_at"])
        _event(
            asset, actor, AssetEvent.EventType.STATUS_CHANGED,
            f"Status changed from {old_status.name} to {new_status.name}.",
            {"from": old_status.code, "to": new_status.code, "reason": (reason or "").strip()},
        )
    return asset


def assign_custody(*, asset, custodian, actor, reason=""):
    with transaction.atomic():
        open_rows = list(AssetCustody.objects.filter(asset=asset, returned_at__isnull=True))
        if open_rows:
            AssetCustody.objects.filter(id__in=[row.id for row in open_rows]).update(returned_at=timezone.now())
            _event(asset, actor, AssetEvent.EventType.CUSTODY_RETURNED, "Previous custody assignment closed.")
        if custodian:
            AssetCustody.objects.create(
                asset=asset, custodian=custodian, assigned_at=timezone.now(), assigned_by=actor,
                reason=(reason or "").strip(),
            )
        asset.current_custodian = custodian
        asset.save(update_fields=["current_custodian", "updated_at"])
        if custodian:
            _event(asset, actor, AssetEvent.EventType.CUSTODY_ASSIGNED, f"Custody assigned to {custodian}.")
    return asset


def add_evidence(*, asset, uploaded_file, kind, actor, notes=""):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    mime_type = getattr(uploaded_file, "content_type", "") or mimetypes.guess_type(uploaded_file.name)[0] or ""
    evidence = AssetEvidence.objects.create(
        asset=asset,
        kind=kind,
        file=uploaded_file,
        original_filename=uploaded_file.name,
        mime_type=mime_type,
        size_bytes=getattr(uploaded_file, "size", 0),
        sha256=digest.hexdigest(),
        uploaded_by=actor,
        notes=(notes or "").strip(),
    )
    _event(asset, actor, AssetEvent.EventType.EVIDENCE_ADDED, f"Added {evidence.get_kind_display()} evidence.")
    return evidence


def update_asset_details(
    *, asset, actor, ownership, manufacturer, model, serial_number, acquired_at, notes,
    automatic_allocation_enabled=True, allocation_hold=False, allocation_hold_reason="",
):
    before = {
        "ownership": asset.ownership,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "acquired_at": asset.acquired_at.isoformat() if asset.acquired_at else None,
        "notes": asset.notes,
        "automatic_allocation_enabled": asset.automatic_allocation_enabled,
        "allocation_hold": asset.allocation_hold,
        "allocation_hold_reason": asset.allocation_hold_reason,
    }
    with transaction.atomic():
        asset.ownership = ownership
        asset.manufacturer = (manufacturer or "").strip()
        asset.model = (model or "").strip()
        asset.serial_number = (serial_number or "").strip()
        asset.acquired_at = acquired_at
        asset.notes = (notes or "").strip()
        asset.automatic_allocation_enabled = bool(automatic_allocation_enabled)
        asset.allocation_hold = bool(allocation_hold)
        asset.allocation_hold_reason = (allocation_hold_reason or "").strip()[:240] if asset.allocation_hold else ""
        asset.save()
        after = {
            "ownership": asset.ownership,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "acquired_at": asset.acquired_at.isoformat() if asset.acquired_at else None,
            "notes": asset.notes,
            "automatic_allocation_enabled": asset.automatic_allocation_enabled,
            "allocation_hold": asset.allocation_hold,
            "allocation_hold_reason": asset.allocation_hold_reason,
        }
        _event(asset, actor, AssetEvent.EventType.UPDATED, "Asset details updated.", {"before": before, "after": after})
    return asset

# ---------------------------------------------------------------------------
# Asset request / reservation services
# ---------------------------------------------------------------------------

from .models import AssetRequest, AssetRequestEvent, AssetRequestItem

ASSET_REQUEST_SUFFIX_BYTES = 3
ASSET_REQUEST_NUMBER_MAX_ATTEMPTS = 32
# BAM lifecycle states that are not candidates for a new reservation. Storage is
# intentionally eligible: an item in storage may be brought into service.
NON_ALLOCATABLE_ASSET_STATUS_CODES = {"RESERVED", "REPAIR", "LOST", "RETIRED", "DISPOSED"}


def _request_event(asset_request, actor, event_type, summary, metadata=None):
    return AssetRequestEvent.objects.create(
        request=asset_request,
        actor=actor,
        event_type=event_type,
        summary=summary,
        metadata=metadata or {},
    )


def _generate_asset_request_number():
    year = date.today().year % 100
    suffix = secrets.token_hex(ASSET_REQUEST_SUFFIX_BYTES).upper()
    return f"BAMR-{year:02d}-{suffix}"


def _validate_request_window(requested_start, requested_end):
    if not requested_start or not requested_end:
        raise ValidationError("Requested start and end dates are required.")
    if requested_end < requested_start:
        raise ValidationError("Requested end date cannot be before the start date.")


def _validate_item_preference(*, department, asset_type, preference_mode, preferred_asset):
    if preference_mode not in AssetRequestItem.PreferenceMode.values:
        raise ValidationError("Unknown asset allocation preference.")

    if preference_mode in {
        AssetRequestItem.PreferenceMode.PREFER,
        AssetRequestItem.PreferenceMode.REQUIRE,
    } and preferred_asset is None:
        raise ValidationError("A preferred asset is required for this allocation preference.")

    if preferred_asset is not None:
        if preferred_asset.department_id != department.pk:
            raise ValidationError("Preferred asset does not belong to the requested department.")
        if preferred_asset.asset_type_id != asset_type.pk:
            raise ValidationError("Preferred asset does not match the requested asset type.")


def _busy_asset_ids(*, requested_start, requested_end, exclude_item_id=None):
    # An active checkout blocks its own reserved window. Once that window has
    # expired without a return, it becomes overdue and blocks all future
    # allocations until custody is explicitly returned or handed off. This
    # still allows a non-overlapping next-day reservation to be approved while
    # today's checkout is active, which is required for direct handoffs.
    today = timezone.localdate()
    qs = AssetRequestItem.objects.filter(allocated_asset__isnull=False).filter(
        Q(
            status=AssetRequestItem.Status.CHECKED_OUT,
            request__requested_end__lt=today,
        )
        | Q(
            status__in=[
                AssetRequestItem.Status.ALLOCATED,
                AssetRequestItem.Status.CHECKED_OUT,
            ],
            request__requested_start__lte=requested_end,
            request__requested_end__gte=requested_start,
        )
    )
    if exclude_item_id:
        qs = qs.exclude(pk=exclude_item_id)
    return qs.values("allocated_asset_id")


def eligible_assets_for_item(item, *, respect_automation_policy=True):
    """Return assets that can satisfy an item for its requested date window.

    Reservation conflicts always matter. Automatic matching also requires the
    asset to be in stock/default custody (or unassigned), enabled for automation,
    and free of an allocation hold. Explicit manager selection may bypass the
    automation opt-out/custody preference, but never a hard allocation hold.
    """
    busy_ids = _busy_asset_ids(
        requested_start=item.request.requested_start,
        requested_end=item.request.requested_end,
        exclude_item_id=item.pk,
    )
    qs = Asset.objects.filter(
        department=item.department,
        asset_type=item.asset_type,
        status__is_terminal=False,
        allocation_hold=False,
    )
    if respect_automation_policy:
        qs = qs.filter(automatic_allocation_enabled=True)
        stock_custodian = get_bam_default_custodian()
        if stock_custodian is not None:
            qs = qs.filter(Q(current_custodian__isnull=True) | Q(current_custodian=stock_custodian))
        else:
            qs = qs.filter(current_custodian__isnull=True)
    return (
        qs
        .exclude(status__code__in=NON_ALLOCATABLE_ASSET_STATUS_CODES)
        .exclude(pk__in=busy_ids)
        .select_related("department", "asset_type", "status", "current_custodian")
        .order_by("asset_id")
    )


def asset_reservation_conflicts(*, asset, requested_start, requested_end, exclude_item_id=None):
    today = timezone.localdate()
    qs = AssetRequestItem.objects.filter(allocated_asset=asset).filter(
        Q(
            status=AssetRequestItem.Status.CHECKED_OUT,
            request__requested_end__lt=today,
        )
        | Q(
            status__in=[
                AssetRequestItem.Status.ALLOCATED,
                AssetRequestItem.Status.CHECKED_OUT,
            ],
            request__requested_start__lte=requested_end,
            request__requested_end__gte=requested_start,
        )
    ).select_related("request", "request__requester")
    if exclude_item_id:
        qs = qs.exclude(pk=exclude_item_id)
    return qs.order_by("request__requested_start", "created_at")


def _asset_is_available_for_item(*, asset, item, respect_automation_policy=True):
    if asset.department_id != item.department_id or asset.asset_type_id != item.asset_type_id:
        return False
    if asset.status.is_terminal or asset.status.code in NON_ALLOCATABLE_ASSET_STATUS_CODES:
        return False
    if asset.allocation_hold:
        return False
    if respect_automation_policy:
        if not asset.automatic_allocation_enabled:
            return False
        stock_custodian = get_bam_default_custodian()
        if asset.current_custodian_id and (
            stock_custodian is None or asset.current_custodian_id != stock_custodian.pk
        ):
            return False
    # Use a locking read here. Allocation callers already hold the Asset row
    # lock; a locking conflict query ensures a concurrent allocator that waited
    # on that row sees reservations committed by the transaction ahead of it
    # instead of relying on a stale REPEATABLE READ snapshot.
    return not asset_reservation_conflicts(
        asset=asset,
        requested_start=item.request.requested_start,
        requested_end=item.request.requested_end,
        exclude_item_id=item.pk,
    ).select_for_update().exists()


def _refresh_request_status(asset_request):
    """Derive request status from requirement states unless request is terminal."""
    if asset_request.status in {
        AssetRequest.Status.DENIED,
        AssetRequest.Status.CANCELLED,
        AssetRequest.Status.COMPLETED,
    }:
        return asset_request.status

    statuses = list(asset_request.items.values_list("status", flat=True))
    if not statuses:
        new_status = AssetRequest.Status.SUBMITTED
    else:
        terminal_item_statuses = {
            AssetRequestItem.Status.DENIED,
            AssetRequestItem.Status.CANCELLED,
            AssetRequestItem.Status.RELEASED,
            AssetRequestItem.Status.RETURNED,
        }
        active = [s for s in statuses if s not in terminal_item_statuses]
        allocated_count = statuses.count(AssetRequestItem.Status.ALLOCATED)
        checked_out_count = statuses.count(AssetRequestItem.Status.CHECKED_OUT)
        waiting_count = statuses.count(AssetRequestItem.Status.WAITLISTED)
        pending_count = statuses.count(AssetRequestItem.Status.PENDING)

        if not active and any(
            s in {AssetRequestItem.Status.RELEASED, AssetRequestItem.Status.RETURNED}
            for s in statuses
        ):
            new_status = AssetRequest.Status.COMPLETED
        elif not active and statuses and all(s == AssetRequestItem.Status.CANCELLED for s in statuses):
            new_status = AssetRequest.Status.CANCELLED
        elif not active and AssetRequestItem.Status.DENIED in statuses:
            new_status = AssetRequest.Status.DENIED
        elif checked_out_count and checked_out_count == len(active):
            new_status = (
                AssetRequest.Status.PARTIALLY_CHECKED_OUT
                if len(active) < len(statuses)
                else AssetRequest.Status.CHECKED_OUT
            )
        elif checked_out_count:
            new_status = AssetRequest.Status.PARTIALLY_CHECKED_OUT
        elif active and allocated_count == len(active):
            new_status = (
                AssetRequest.Status.PARTIALLY_RESERVED
                if len(active) < len(statuses)
                else AssetRequest.Status.RESERVED
            )
        elif allocated_count:
            new_status = AssetRequest.Status.PARTIALLY_RESERVED
        elif waiting_count:
            new_status = AssetRequest.Status.QUEUED
        elif pending_count:
            new_status = AssetRequest.Status.SUBMITTED
        else:
            new_status = AssetRequest.Status.SUBMITTED

    if asset_request.status != new_status:
        AssetRequest.objects.filter(pk=asset_request.pk).update(status=new_status, updated_at=timezone.now())
        asset_request.status = new_status
    return new_status


def create_asset_request(
    *,
    actor,
    purpose,
    requested_start,
    requested_end,
    department,
    asset_type,
    preference_mode,
    preferred_asset=None,
    justification="",
    priority=AssetRequest.Priority.NORMAL,
    desired_completion_date=None,
    related_ticket=None,
    item_note="",
    apply_automation=False,
):
    _validate_request_window(requested_start, requested_end)
    if desired_completion_date and desired_completion_date < requested_start:
        raise ValidationError("Desired completion date cannot be before the requested start date.")
    _validate_item_preference(
        department=department,
        asset_type=asset_type,
        preference_mode=preference_mode,
        preferred_asset=preferred_asset,
    )
    if priority not in AssetRequest.Priority.values:
        raise ValidationError("Unknown asset request priority.")

    if related_ticket is not None:
        from apps.shit.permissions import can_view_ticket
        if not can_view_ticket(actor, related_ticket):
            raise ValidationError("You cannot reference a SHIT ticket you cannot view.")

    for _ in range(ASSET_REQUEST_NUMBER_MAX_ATTEMPTS):
        request_number = _generate_asset_request_number()
        try:
            with transaction.atomic():
                asset_request = AssetRequest.objects.create(
                    request_number=request_number,
                    requester=actor,
                    related_ticket=related_ticket,
                    purpose=(purpose or "").strip(),
                    justification=(justification or "").strip(),
                    priority=priority,
                    status=AssetRequest.Status.SUBMITTED,
                    requested_start=requested_start,
                    requested_end=requested_end,
                    desired_completion_date=desired_completion_date,
                )
                item = AssetRequestItem.objects.create(
                    request=asset_request,
                    department=department,
                    asset_type=asset_type,
                    preference_mode=preference_mode,
                    preferred_asset=(
                        None if preference_mode == AssetRequestItem.PreferenceMode.ANY else preferred_asset
                    ),
                    status=AssetRequestItem.Status.PENDING,
                    note=(item_note or "").strip(),
                )
                _request_event(
                    asset_request,
                    actor,
                    AssetRequestEvent.EventType.CREATED,
                    f"Asset request created as {asset_request.request_number}.",
                    {
                        "department": department.code,
                        "asset_type": asset_type.code,
                        "preference_mode": preference_mode,
                        "preferred_asset": preferred_asset.asset_id if preferred_asset else None,
                        "related_ticket": related_ticket.ticket_number if related_ticket else None,
                    },
                )
            if apply_automation:
                item = auto_process_request_item(item=item, fallback_actor=actor)
                asset_request.refresh_from_db()
            return asset_request, item
        except IntegrityError as exc:
            if _is_duplicate_key(exc):
                continue
            raise
    raise RuntimeError("Unable to allocate a unique BAM request number after repeated attempts.")

def add_asset_request_item(
    *, asset_request, actor, department, asset_type, preference_mode,
    preferred_asset=None, note="", apply_automation=False,
):
    if asset_request.status in {
        AssetRequest.Status.DENIED,
        AssetRequest.Status.CANCELLED,
        AssetRequest.Status.COMPLETED,
    }:
        raise ValidationError("Requirements cannot be added to a closed asset request.")

    _validate_item_preference(
        department=department,
        asset_type=asset_type,
        preference_mode=preference_mode,
        preferred_asset=preferred_asset,
    )
    with transaction.atomic():
        locked_request = AssetRequest.objects.select_for_update().get(pk=asset_request.pk)
        item = AssetRequestItem.objects.create(
            request=locked_request,
            department=department,
            asset_type=asset_type,
            preference_mode=preference_mode,
            preferred_asset=(
                None if preference_mode == AssetRequestItem.PreferenceMode.ANY else preferred_asset
            ),
            status=AssetRequestItem.Status.PENDING,
            note=(note or "").strip(),
        )
        _request_event(
            locked_request,
            actor,
            AssetRequestEvent.EventType.ITEM_ADDED,
            f"Added {department.code} {asset_type.name} requirement.",
            {
                "item_id": str(item.pk),
                "preference_mode": preference_mode,
                "preferred_asset": preferred_asset.asset_id if preferred_asset else None,
            },
        )
        _refresh_request_status(locked_request)
    if apply_automation:
        return auto_process_request_item(item=item, fallback_actor=actor)
    return item

def _least_recently_allocated_candidate(
    item, *, exclude_asset_ids=None, respect_automation_policy=True
):
    """Choose an eligible asset deterministically, spreading reuse over the pool."""
    from django.db.models import Max

    exclude_asset_ids = set(exclude_asset_ids or [])
    qs = eligible_assets_for_item(
        item, respect_automation_policy=respect_automation_policy
    ).exclude(pk__in=exclude_asset_ids).annotate(
        last_allocated_at=Max("allocated_request_items__allocated_at")
    ).order_by("last_allocated_at", "asset_id")
    return qs.first()


def allocate_request_item(*, item, actor, selected_asset=None, allow_equivalent=True, automated=False):
    """Reserve an asset for a request item or place it onto its waitlist.

    This operation never changes Asset.current_custodian. Reservation and custody
    are intentionally separate state machines.
    """
    with transaction.atomic():
        locked_item = (
            AssetRequestItem.objects.select_for_update()
            .select_related(
                "request", "department", "asset_type", "preferred_asset",
                "allocated_asset", "preferred_asset__status",
            )
            .get(pk=item.pk)
        )
        asset_request = AssetRequest.objects.select_for_update().get(pk=locked_item.request_id)
        locked_item.request = asset_request

        if asset_request.status in {
            AssetRequest.Status.DENIED,
            AssetRequest.Status.CANCELLED,
            AssetRequest.Status.COMPLETED,
        }:
            raise ValidationError("Closed asset requests cannot be allocated.")
        if locked_item.status in {
            AssetRequestItem.Status.ALLOCATED,
            AssetRequestItem.Status.CHECKED_OUT,
        }:
            raise ValidationError("This requirement is already reserved or checked out.")
        if locked_item.status in {
            AssetRequestItem.Status.RELEASED,
            AssetRequestItem.Status.RETURNED,
            AssetRequestItem.Status.DENIED,
            AssetRequestItem.Status.CANCELLED,
        }:
            raise ValidationError("This requirement is closed and cannot be allocated.")

        candidate = None
        if selected_asset is not None:
            if selected_asset.department_id != locked_item.department_id or selected_asset.asset_type_id != locked_item.asset_type_id:
                raise ValidationError("Selected asset does not match this request requirement.")
            if (
                locked_item.preference_mode == AssetRequestItem.PreferenceMode.REQUIRE
                and selected_asset.pk != locked_item.preferred_asset_id
            ):
                raise ValidationError("This request requires the exact preferred asset; an equivalent cannot be substituted.")
            candidate = Asset.objects.select_for_update().select_related("status").get(pk=selected_asset.pk)
            if not _asset_is_available_for_item(
                asset=candidate, item=locked_item, respect_automation_policy=automated
            ):
                raise ValidationError(f"{candidate.asset_id} is unavailable for the requested window.")
        else:
            preferred = locked_item.preferred_asset
            if locked_item.preference_mode in {
                AssetRequestItem.PreferenceMode.PREFER,
                AssetRequestItem.PreferenceMode.REQUIRE,
            } and preferred is not None:
                preferred_locked = Asset.objects.select_for_update().select_related("status").get(pk=preferred.pk)
                if _asset_is_available_for_item(
                    asset=preferred_locked,
                    item=locked_item,
                    respect_automation_policy=automated,
                ):
                    candidate = preferred_locked
                elif locked_item.preference_mode == AssetRequestItem.PreferenceMode.REQUIRE:
                    candidate = None

            if candidate is None and locked_item.preference_mode != AssetRequestItem.PreferenceMode.REQUIRE and allow_equivalent:
                # Select the least recently allocated eligible equivalent. Lock and
                # re-check the row so concurrent approvers cannot double-reserve it.
                skipped = set()
                while True:
                    possible = _least_recently_allocated_candidate(
                        locked_item,
                        exclude_asset_ids=skipped,
                        respect_automation_policy=automated,
                    )
                    if possible is None:
                        break
                    possible_locked = Asset.objects.select_for_update().select_related("status").get(pk=possible.pk)
                    if _asset_is_available_for_item(
                        asset=possible_locked,
                        item=locked_item,
                        respect_automation_policy=automated,
                    ):
                        candidate = possible_locked
                        break
                    skipped.add(possible.pk)

        if candidate is None:
            # Reconciliation pulses may revisit an already-waitlisted item many
            # times while its requested asset remains unavailable. Keep that
            # retry path idempotent instead of writing a duplicate WAITLISTED
            # event on every automation pulse.
            was_waitlisted = locked_item.status == AssetRequestItem.Status.WAITLISTED
            locked_item.status = AssetRequestItem.Status.WAITLISTED
            locked_item.allocated_asset = None
            locked_item.allocated_by = None
            locked_item.allocated_at = None
            locked_item.released_at = None
            locked_item.save(update_fields=[
                "status", "allocated_asset", "allocated_by", "allocated_at",
                "released_at", "updated_at",
            ])
            if not was_waitlisted:
                _request_event(
                    asset_request,
                    actor,
                    AssetRequestEvent.EventType.WAITLISTED,
                    f"{locked_item.asset_type.name} requirement placed on the waitlist.",
                    _automatic_event_metadata({
                        "item_id": str(locked_item.pk),
                        "preferred_asset": locked_item.preferred_asset.asset_id if locked_item.preferred_asset else None,
                        "preference_mode": locked_item.preference_mode,
                    }) if automated else {
                        "item_id": str(locked_item.pk),
                        "preferred_asset": locked_item.preferred_asset.asset_id if locked_item.preferred_asset else None,
                        "preference_mode": locked_item.preference_mode,
                    },
                )
            _refresh_request_status(asset_request)
            return locked_item

        locked_item.status = AssetRequestItem.Status.ALLOCATED
        locked_item.allocated_asset = candidate
        locked_item.allocated_by = actor
        locked_item.allocated_at = timezone.now()
        locked_item.released_at = None
        locked_item.save(update_fields=[
            "status", "allocated_asset", "allocated_by", "allocated_at",
            "released_at", "updated_at",
        ])
        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.ALLOCATED,
            f"Reserved {candidate.asset_id} for this request.",
            _automatic_event_metadata({"item_id": str(locked_item.pk), "asset_id": candidate.asset_id}) if automated else {"item_id": str(locked_item.pk), "asset_id": candidate.asset_id},
        )
        _event(
            candidate,
            actor,
            AssetEvent.EventType.RESERVATION_ALLOCATED,
            f"Reserved for {asset_request.request_number} ({asset_request.requested_start} through {asset_request.requested_end}).",
            _automatic_event_metadata({"asset_request": asset_request.request_number, "item_id": str(locked_item.pk)}) if automated else {"asset_request": asset_request.request_number, "item_id": str(locked_item.pk)},
        )
        _refresh_request_status(asset_request)
        return locked_item


def auto_process_request_item(*, item, fallback_actor):
    """Apply BAM automation policy to a newly submitted requirement."""
    settings_obj = get_bam_automation_settings()
    if not settings_obj.auto_approve_available_requests:
        return AssetRequestItem.objects.select_related("allocated_asset", "request").get(pk=item.pk)

    actor = get_bam_automation_actor(fallback_actor)
    result = allocate_request_item(
        item=item,
        actor=actor,
        allow_equivalent=settings_obj.allow_equivalent_substitution,
        automated=True,
    )
    if (
        result.status == AssetRequestItem.Status.ALLOCATED
        and settings_obj.auto_transfer_on_approval
        and result.request.requested_start <= timezone.localdate() <= result.request.requested_end
    ):
        issue_checkout(
            item=result,
            actor=actor,
            notes="Automatic BAM checkout on approval",
            automated=True,
        )
        result.refresh_from_db()
    return result


def _active_reserved_item_for_asset(asset):
    today = timezone.localdate()
    return (
        AssetRequestItem.objects.filter(
            allocated_asset=asset,
            status=AssetRequestItem.Status.ALLOCATED,
            request__requested_start__lte=today,
            request__requested_end__gte=today,
        )
        .select_related("request", "request__requester", "department", "asset_type")
        .order_by("request__requested_start", "request__created_at", "created_at")
        .first()
    )


def auto_issue_ready_reservation_for_asset(*, asset, fallback_actor):
    settings_obj = get_bam_automation_settings()
    if not settings_obj.auto_transfer_on_release:
        return None
    item = _active_reserved_item_for_asset(asset)
    if item is None:
        return None
    actor = get_bam_automation_actor(fallback_actor)
    try:
        return issue_checkout(
            item=item,
            actor=actor,
            notes="Automatic BAM transfer after prior custodian release",
            automated=True,
        )
    except ValidationError:
        return None


def release_request_item(*, item, actor, reason=""):
    promoted_asset_id = None
    with transaction.atomic():
        locked_item = (
            AssetRequestItem.objects.select_for_update()
            .select_related("request", "allocated_asset")
            .get(pk=item.pk)
        )
        if locked_item.status == AssetRequestItem.Status.CHECKED_OUT:
            raise ValidationError("Return the checked-out asset before releasing its reservation.")
        if locked_item.status != AssetRequestItem.Status.ALLOCATED or locked_item.allocated_asset is None:
            raise ValidationError("Only an active reservation can be released.")
        asset_request = AssetRequest.objects.select_for_update().get(pk=locked_item.request_id)
        asset = locked_item.allocated_asset
        locked_item.status = AssetRequestItem.Status.RELEASED
        locked_item.released_at = timezone.now()
        locked_item.save(update_fields=["status", "released_at", "updated_at"])
        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.RELEASED,
            f"Released reservation for {asset.asset_id}.",
            {"item_id": str(locked_item.pk), "asset_id": asset.asset_id, "reason": (reason or "").strip()},
        )
        _event(
            asset,
            actor,
            AssetEvent.EventType.RESERVATION_RELEASED,
            f"Reservation for {asset_request.request_number} released.",
            {"asset_request": asset_request.request_number, "item_id": str(locked_item.pk), "reason": (reason or "").strip()},
        )
        new_status = _refresh_request_status(asset_request)
        if new_status == AssetRequest.Status.COMPLETED:
            _request_event(
                asset_request,
                actor,
                AssetRequestEvent.EventType.COMPLETED,
                "All reservation requirements are closed; request completed.",
            )
        promoted_asset_id = asset.pk

    promoted = promote_waitlist_for_asset(asset=Asset.objects.get(pk=promoted_asset_id), actor=actor)
    return locked_item, promoted


def deny_asset_request_item(*, item, actor, reason=""):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required when denying an asset requirement.")
    with transaction.atomic():
        locked_item = (
            AssetRequestItem.objects.select_for_update()
            .select_related("request", "asset_type")
            .get(pk=item.pk)
        )
        if locked_item.status not in {
            AssetRequestItem.Status.PENDING,
            AssetRequestItem.Status.WAITLISTED,
        }:
            raise ValidationError("Only pending or waitlisted requirements can be denied.")
        asset_request = AssetRequest.objects.select_for_update().get(pk=locked_item.request_id)
        locked_item.status = AssetRequestItem.Status.DENIED
        locked_item.save(update_fields=["status", "updated_at"])
        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.DENIED,
            f"Denied {locked_item.asset_type.name} requirement.",
            {"item_id": str(locked_item.pk), "reason": reason},
        )
        _refresh_request_status(asset_request)
        return locked_item


def cancel_asset_request_item(*, item, actor, reason=""):
    with transaction.atomic():
        locked_item = (
            AssetRequestItem.objects.select_for_update()
            .select_related("request")
            .get(pk=item.pk)
        )
        if locked_item.status not in {
            AssetRequestItem.Status.PENDING,
            AssetRequestItem.Status.WAITLISTED,
        }:
            raise ValidationError("Only pending or waitlisted requirements can be removed.")
        asset_request = AssetRequest.objects.select_for_update().get(pk=locked_item.request_id)
        locked_item.status = AssetRequestItem.Status.CANCELLED
        locked_item.save(update_fields=["status", "updated_at"])
        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.CANCELLED,
            f"Removed {locked_item.asset_type.name} requirement.",
            {"item_id": str(locked_item.pk), "reason": (reason or "").strip()},
        )
        _refresh_request_status(asset_request)
        return locked_item


def cancel_asset_request(*, asset_request, actor, reason=""):
    with transaction.atomic():
        locked_request = AssetRequest.objects.select_for_update().get(pk=asset_request.pk)
        if locked_request.status in {
            AssetRequest.Status.CANCELLED,
            AssetRequest.Status.DENIED,
            AssetRequest.Status.COMPLETED,
        }:
            raise ValidationError("This asset request is already closed.")
        if locked_request.items.filter(status__in=[AssetRequestItem.Status.ALLOCATED, AssetRequestItem.Status.CHECKED_OUT]).exists():
            raise ValidationError("Return checked-out assets and release active reservations before cancelling the request.")
        locked_request.items.filter(
            status__in=[AssetRequestItem.Status.PENDING, AssetRequestItem.Status.WAITLISTED]
        ).update(status=AssetRequestItem.Status.CANCELLED, updated_at=timezone.now())
        locked_request.status = AssetRequest.Status.CANCELLED
        locked_request.save(update_fields=["status", "updated_at"])
        _request_event(
            locked_request, actor, AssetRequestEvent.EventType.CANCELLED,
            "Asset request cancelled.", {"reason": (reason or "").strip()},
        )
        return locked_request


def deny_asset_request(*, asset_request, actor, reason=""):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required when denying an asset request.")
    with transaction.atomic():
        locked_request = AssetRequest.objects.select_for_update().get(pk=asset_request.pk)
        if locked_request.status in {
            AssetRequest.Status.CANCELLED,
            AssetRequest.Status.DENIED,
            AssetRequest.Status.COMPLETED,
        }:
            raise ValidationError("This asset request is already closed.")
        if locked_request.items.filter(status__in=[AssetRequestItem.Status.ALLOCATED, AssetRequestItem.Status.CHECKED_OUT]).exists():
            raise ValidationError("Return checked-out assets and release active reservations before denying the request.")
        locked_request.items.filter(
            status__in=[AssetRequestItem.Status.PENDING, AssetRequestItem.Status.WAITLISTED]
        ).update(status=AssetRequestItem.Status.DENIED, updated_at=timezone.now())
        locked_request.status = AssetRequest.Status.DENIED
        locked_request.save(update_fields=["status", "updated_at"])
        _request_event(
            locked_request, actor, AssetRequestEvent.EventType.DENIED,
            "Asset request denied.", {"reason": reason},
        )
        return locked_request


def complete_asset_request(*, asset_request, actor, reason=""):
    with transaction.atomic():
        locked_request = AssetRequest.objects.select_for_update().get(pk=asset_request.pk)
        if locked_request.items.filter(
            status__in=[
                AssetRequestItem.Status.PENDING,
                AssetRequestItem.Status.WAITLISTED,
                AssetRequestItem.Status.ALLOCATED,
                AssetRequestItem.Status.CHECKED_OUT,
            ]
        ).exists():
            raise ValidationError("Resolve or release all outstanding requirements before completing the request.")
        if locked_request.status in {AssetRequest.Status.CANCELLED, AssetRequest.Status.DENIED}:
            raise ValidationError("Cancelled or denied requests cannot be completed.")
        locked_request.status = AssetRequest.Status.COMPLETED
        locked_request.save(update_fields=["status", "updated_at"])
        _request_event(
            locked_request, actor, AssetRequestEvent.EventType.COMPLETED,
            "Asset request completed.", {"reason": (reason or "").strip()},
        )
        return locked_request


def waitlist_position(item):
    if item.status != AssetRequestItem.Status.WAITLISTED:
        return None
    qs = AssetRequestItem.objects.filter(
        status=AssetRequestItem.Status.WAITLISTED,
        request__requested_start__lte=item.request.requested_end,
        request__requested_end__gte=item.request.requested_start,
    )
    if item.preference_mode == AssetRequestItem.PreferenceMode.REQUIRE and item.preferred_asset_id:
        qs = qs.filter(preferred_asset_id=item.preferred_asset_id)
    else:
        qs = qs.filter(department_id=item.department_id, asset_type_id=item.asset_type_id)
    ids = list(qs.order_by("request__created_at", "created_at", "pk").values_list("pk", flat=True))
    try:
        return ids.index(item.pk) + 1
    except ValueError:
        return None

# ---------------------------------------------------------------------------
# Checkout / physical custody services
# ---------------------------------------------------------------------------


def checkout_is_overdue(checkout, *, on_date=None):
    on_date = on_date or timezone.localdate()
    return checkout.returned_at is None and checkout.request_item.request.requested_end < on_date


def handoff_candidates_for_checkout(checkout, *, on_date=None):
    """Approved reservations on the same asset that can accept a direct handoff.

    A next-day reservation is eligible so a manager can hand the asset directly
    to the next approved user instead of forcing a pointless overnight return
    to inventory.
    """
    on_date = on_date or timezone.localdate()
    latest_start = on_date + timedelta(days=1)
    return (
        AssetRequestItem.objects.filter(
            allocated_asset=checkout.asset,
            status=AssetRequestItem.Status.ALLOCATED,
            request__requested_start__lte=latest_start,
            request__requested_end__gte=on_date,
        )
        .exclude(pk=checkout.request_item_id)
        .select_related("request", "request__requester", "department", "asset_type")
        .order_by("request__requested_start", "request__created_at", "created_at")
    )


def issue_checkout(*, item, actor, notes="", automated=False):
    """Convert an approved reservation into physical custody."""
    today = timezone.localdate()
    with transaction.atomic():
        locked_item = (
            AssetRequestItem.objects.select_for_update()
            .select_related("request", "request__requester", "allocated_asset", "department")
            .get(pk=item.pk)
        )
        asset_request = AssetRequest.objects.select_for_update().get(pk=locked_item.request_id)
        locked_item.request = asset_request

        if locked_item.status != AssetRequestItem.Status.ALLOCATED or locked_item.allocated_asset_id is None:
            raise ValidationError("Only an active reservation can be checked out.")
        if not (asset_request.requested_start <= today <= asset_request.requested_end):
            raise ValidationError("This reservation can only be checked out during its requested date window.")

        asset = Asset.objects.select_for_update().select_related("status").get(pk=locked_item.allocated_asset_id)
        if asset.status.is_terminal or asset.status.code in NON_ALLOCATABLE_ASSET_STATUS_CODES:
            raise ValidationError(f"{asset.asset_id} cannot be checked out in its current BAM status.")
        if AssetCheckout.objects.select_for_update().filter(asset=asset, returned_at__isnull=True).exists():
            raise ValidationError(f"{asset.asset_id} is already checked out.")
        if automated:
            stock_custodian = get_bam_default_custodian()
            if asset.current_custodian_id and (stock_custodian is None or asset.current_custodian_id != stock_custodian.pk):
                raise ValidationError(f"{asset.asset_id} is in custody and cannot be transferred automatically.")

        checkout = AssetCheckout.objects.create(
            request_item=locked_item,
            asset=asset,
            custodian=asset_request.requester,
            issued_by=actor,
            notes=(notes or "").strip(),
        )
        assign_custody(
            asset=asset,
            custodian=asset_request.requester,
            actor=actor,
            reason=f"Checkout for {asset_request.request_number}",
        )
        locked_item.status = AssetRequestItem.Status.CHECKED_OUT
        locked_item.save(update_fields=["status", "updated_at"])

        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.CHECKED_OUT,
            f"Checked out {asset.asset_id} to {asset_request.requester}.",
            _automatic_event_metadata({"item_id": str(locked_item.pk), "asset_id": asset.asset_id, "checkout_id": str(checkout.pk)}) if automated else {"item_id": str(locked_item.pk), "asset_id": asset.asset_id, "checkout_id": str(checkout.pk)},
        )
        _event(
            asset,
            actor,
            AssetEvent.EventType.CHECKOUT_ISSUED,
            "Reservation-backed checkout issued.",
            _automatic_event_metadata({"asset_request": asset_request.request_number, "item_id": str(locked_item.pk), "checkout_id": str(checkout.pk)}) if automated else {"asset_request": asset_request.request_number, "item_id": str(locked_item.pk), "checkout_id": str(checkout.pk)},
        )
        _refresh_request_status(asset_request)
        return checkout


def return_checkout(
    *, checkout, actor, reason="",
    condition=AssetCheckout.ReturnCondition.GOOD,
    condition_notes="",
    apply_automation=False,
):
    """Close physical custody, return stock to Vanguard/default, and run queue automation."""
    reason = (reason or "").strip()
    condition_notes = (condition_notes or "").strip()
    if condition not in AssetCheckout.ReturnCondition.values:
        raise ValidationError("Unknown asset return condition.")

    settings_obj = get_bam_automation_settings()
    stock_custodian = get_bam_default_custodian()
    promoted_asset_id = None

    with transaction.atomic():
        locked_checkout = (
            AssetCheckout.objects.select_for_update()
            .select_related(
                "request_item",
                "request_item__request",
                "request_item__request__requester",
                "asset",
            )
            .get(pk=checkout.pk)
        )
        if locked_checkout.returned_at is not None:
            raise ValidationError("This checkout has already been returned.")

        item = AssetRequestItem.objects.select_for_update().get(pk=locked_checkout.request_item_id)
        asset_request = AssetRequest.objects.select_for_update().get(pk=item.request_id)
        asset = Asset.objects.select_for_update().get(pk=locked_checkout.asset_id)
        now = timezone.now()

        if item.status != AssetRequestItem.Status.CHECKED_OUT:
            raise ValidationError("Checkout state is inconsistent with the reservation requirement.")

        locked_checkout.returned_at = now
        locked_checkout.returned_by = actor
        locked_checkout.return_reason = reason
        locked_checkout.return_condition = condition
        locked_checkout.return_notes = condition_notes
        locked_checkout.save(update_fields=[
            "returned_at", "returned_by", "return_reason", "return_condition", "return_notes"
        ])

        item.status = AssetRequestItem.Status.RETURNED
        item.released_at = now
        item.save(update_fields=["status", "released_at", "updated_at"])

        safe_for_reallocation = (
            condition == AssetCheckout.ReturnCondition.GOOD and not asset.allocation_hold
        )
        if not safe_for_reallocation and condition != AssetCheckout.ReturnCondition.GOOD:
            asset.allocation_hold = True
            asset.allocation_hold_reason = (
                condition_notes or f"Release condition: {locked_checkout.get_return_condition_display()}"
            )[:240]
            asset.save(update_fields=["allocation_hold", "allocation_hold_reason", "updated_at"])

        assign_custody(
            asset=asset,
            custodian=stock_custodian,
            actor=actor,
            reason=(
                f"Returned from {asset_request.request_number}"
                + (f": {reason}" if reason else "")
                + (f" · condition {locked_checkout.get_return_condition_display()}" if not safe_for_reallocation else "")
            ),
        )
        _request_event(
            asset_request,
            actor,
            AssetRequestEvent.EventType.RETURNED,
            f"Returned {asset.asset_id} ({locked_checkout.get_return_condition_display()}).",
            {
                "item_id": str(item.pk),
                "asset_id": asset.asset_id,
                "checkout_id": str(locked_checkout.pk),
                "reason": reason,
                "condition": condition,
                "condition_notes": condition_notes,
            },
        )
        _event(
            asset,
            actor,
            AssetEvent.EventType.CHECKOUT_RETURNED,
            "Reservation-backed checkout returned to stock." if safe_for_reallocation else "Checkout returned with allocation hold.",
            {
                "asset_request": asset_request.request_number,
                "item_id": str(item.pk),
                "checkout_id": str(locked_checkout.pk),
                "reason": reason,
                "condition": condition,
                "condition_notes": condition_notes,
                "allocation_hold": not safe_for_reallocation,
            },
        )
        new_status = _refresh_request_status(asset_request)
        if new_status == AssetRequest.Status.COMPLETED:
            _request_event(
                asset_request,
                actor,
                AssetRequestEvent.EventType.COMPLETED,
                "All asset requirements have been returned or released; request completed.",
            )
        promoted_asset_id = asset.pk

    asset = Asset.objects.get(pk=promoted_asset_id)
    promoted = []
    if safe_for_reallocation:
        if apply_automation:
            if settings_obj.auto_promote_waitlist:
                automation_actor = get_bam_automation_actor(actor)
                promoted = promote_waitlist_for_asset(asset=asset, actor=automation_actor, automated=True)
            if settings_obj.auto_transfer_on_release:
                auto_issue_ready_reservation_for_asset(asset=asset, fallback_actor=actor)
        else:
            # Preserve the pre-Chunk-5 manager/manual return behavior: promote
            # the queue, but do not silently issue physical custody.
            promoted = promote_waitlist_for_asset(asset=asset, actor=actor, automated=False)
    return locked_checkout, promoted


def self_release_checkout(*, checkout, actor, condition, notes=""):
    """End-user release. Only the active custodian may release their own checkout."""
    current = AssetCheckout.objects.select_related("asset", "custodian").get(pk=checkout.pk)
    if current.returned_at is not None:
        raise ValidationError("This checkout has already been released.")
    if current.custodian_id != actor.pk:
        raise ValidationError("Only the current custodian can release this asset from their portal.")
    returned, promoted = return_checkout(
        checkout=current,
        actor=actor,
        reason="Released by current custodian",
        condition=condition,
        condition_notes=notes,
        apply_automation=True,
    )
    active_next = AssetCheckout.objects.filter(asset_id=current.asset_id, returned_at__isnull=True).select_related("custodian").first()
    return returned, promoted, active_next

def handoff_checkout(*, checkout, next_item, actor, reason=""):
    """Transfer custody directly from one active checkout to another approved reservation."""
    reason = (reason or "").strip()
    today = timezone.localdate()
    with transaction.atomic():
        current = (
            AssetCheckout.objects.select_for_update()
            .select_related("request_item", "request_item__request", "asset")
            .get(pk=checkout.pk)
        )
        if current.returned_at is not None:
            raise ValidationError("This checkout is already closed.")

        current_item = AssetRequestItem.objects.select_for_update().get(pk=current.request_item_id)
        current_request = AssetRequest.objects.select_for_update().get(pk=current_item.request_id)
        target = (
            AssetRequestItem.objects.select_for_update()
            .select_related("request", "request__requester", "allocated_asset")
            .get(pk=next_item.pk)
        )
        target_request = AssetRequest.objects.select_for_update().get(pk=target.request_id)
        target.request = target_request

        asset = Asset.objects.select_for_update().get(pk=current.asset_id)
        if current_item.status != AssetRequestItem.Status.CHECKED_OUT:
            raise ValidationError("Current checkout state is inconsistent.")
        if target.status != AssetRequestItem.Status.ALLOCATED:
            raise ValidationError("The handoff target must already have an approved reservation.")
        if target.allocated_asset_id != asset.pk:
            raise ValidationError("The handoff target is reserved for a different asset.")
        if not (target_request.requested_start <= today + timedelta(days=1) and target_request.requested_end >= today):
            raise ValidationError("The target reservation is not active or next in line for a direct handoff.")
        if AssetCheckout.objects.filter(request_item=target).exists():
            raise ValidationError("The target reservation already has checkout history.")

        now = timezone.now()
        current.returned_at = now
        current.returned_by = actor
        current.return_reason = reason or f"Direct handoff to {target_request.request_number}"
        current.save(update_fields=["returned_at", "returned_by", "return_reason"])

        current_item.status = AssetRequestItem.Status.RETURNED
        current_item.released_at = now
        current_item.save(update_fields=["status", "released_at", "updated_at"])

        next_checkout = AssetCheckout.objects.create(
            request_item=target,
            asset=asset,
            custodian=target_request.requester,
            issued_by=actor,
            notes=f"Direct handoff from {current_request.request_number}" + (f": {reason}" if reason else ""),
        )
        current.handoff_to = next_checkout
        current.save(update_fields=["handoff_to"])

        # assign_custody closes the prior open custody row and creates the next
        # one atomically, preserving a direct chain with no fake inventory gap.
        assign_custody(
            asset=asset,
            custodian=target_request.requester,
            actor=actor,
            reason=f"Direct handoff {current_request.request_number} → {target_request.request_number}",
        )

        target.status = AssetRequestItem.Status.CHECKED_OUT
        target.save(update_fields=["status", "updated_at"])

        _request_event(
            current_request,
            actor,
            AssetRequestEvent.EventType.HANDOFF,
            f"Handed off {asset.asset_id} to {target_request.request_number}.",
            {"item_id": str(current_item.pk), "asset_id": asset.asset_id, "to_request": target_request.request_number, "reason": reason},
        )
        _request_event(
            target_request,
            actor,
            AssetRequestEvent.EventType.HANDOFF,
            f"Received {asset.asset_id} by direct handoff from {current_request.request_number}.",
            {"item_id": str(target.pk), "asset_id": asset.asset_id, "from_request": current_request.request_number, "reason": reason},
        )
        _event(
            asset,
            actor,
            AssetEvent.EventType.CHECKOUT_HANDOFF,
            "Reservation-backed direct handoff completed.",
            {
                "from_request": current_request.request_number,
                "to_request": target_request.request_number,
                "from_checkout": str(current.pk),
                "to_checkout": str(next_checkout.pk),
                "reason": reason,
            },
        )
        _refresh_request_status(current_request)
        _refresh_request_status(target_request)
        return next_checkout


def promote_waitlist_for_asset(*, asset, actor, automated=False):
    """Reserve a newly available asset for compatible waitlisted work.

    WAITLISTED means a manager has already attempted allocation, so promotion
    does not approve an unreviewed request. Multiple non-overlapping future
    windows may be promoted in one pass because they do not conflict.
    """
    today = timezone.localdate()
    candidates = list(
        AssetRequestItem.objects.filter(
            status=AssetRequestItem.Status.WAITLISTED,
            department=asset.department,
            asset_type=asset.asset_type,
            request__requested_end__gte=today,
        )
        .filter(
            Q(preference_mode__in=[
                AssetRequestItem.PreferenceMode.ANY,
                AssetRequestItem.PreferenceMode.PREFER,
            ])
            | Q(
                preference_mode=AssetRequestItem.PreferenceMode.REQUIRE,
                preferred_asset=asset,
            )
        )
        .select_related("request", "preferred_asset", "department", "asset_type")
        .order_by("request__requested_start", "request__created_at", "created_at", "pk")
    )

    promoted = []
    automation_settings = get_bam_automation_settings() if automated else None
    for candidate in candidates:
        if (
            automated
            and candidate.preference_mode == AssetRequestItem.PreferenceMode.PREFER
            and not automation_settings.allow_equivalent_substitution
            and candidate.preferred_asset_id != asset.pk
        ):
            continue
        try:
            result = allocate_request_item(item=candidate, actor=actor, selected_asset=asset, automated=automated)
        except ValidationError:
            continue
        if result.status == AssetRequestItem.Status.ALLOCATED:
            _request_event(
                result.request,
                actor,
                AssetRequestEvent.EventType.PROMOTED,
                f"Waitlist promoted: {asset.asset_id} is now reserved.",
                _automatic_event_metadata({"item_id": str(result.pk), "asset_id": asset.asset_id})
                if automated else {"item_id": str(result.pk), "asset_id": asset.asset_id},
            )
            promoted.append(result)
    return promoted



def reconcile_asset_automation(*, asset, fallback_actor):
    """Re-evaluate one stock asset after an admin/state change.

    This is the event-driven companion to ``process_due_bam_automation``. It
    prevents a queue entry from remaining stranded when an asset becomes free
    through a manual custody override, status change, or allocation-hold edit
    rather than through the normal self-release endpoint.
    """
    settings_obj = get_bam_automation_settings()
    actor = get_bam_automation_actor(fallback_actor)
    current = Asset.objects.select_related("status", "current_custodian").get(pk=asset.pk)
    stock_custodian = get_bam_default_custodian()

    if current.status.is_terminal or current.status.code in NON_ALLOCATABLE_ASSET_STATUS_CODES:
        return [], None
    if current.allocation_hold or not current.automatic_allocation_enabled:
        return [], None
    if current.current_custodian_id and (
        stock_custodian is None or current.current_custodian_id != stock_custodian.pk
    ):
        return [], None

    promoted = []
    if settings_obj.auto_promote_waitlist:
        promoted = promote_waitlist_for_asset(
            asset=current,
            actor=actor,
            automated=True,
        )

    checkout = None
    if settings_obj.auto_transfer_on_approval:
        ready = _active_reserved_item_for_asset(current)
        if ready is not None:
            try:
                checkout = issue_checkout(
                    item=ready,
                    actor=actor,
                    notes="Automatic BAM checkout after asset became available",
                    automated=True,
                )
            except ValidationError:
                checkout = None
    return promoted, checkout


def waitlist_status_message(item):
    """Return a non-sensitive explanation for why a queued requirement is waiting.

    This is intentionally descriptive rather than authoritative; allocation
    still re-checks every rule under row locks before reserving an asset.
    """
    if item.status != AssetRequestItem.Status.WAITLISTED:
        return ""

    if item.preference_mode in {
        AssetRequestItem.PreferenceMode.PREFER,
        AssetRequestItem.PreferenceMode.REQUIRE,
    } and item.preferred_asset_id:
        asset = item.preferred_asset
        if asset.status.is_terminal or asset.status.code in NON_ALLOCATABLE_ASSET_STATUS_CODES:
            return "Preferred asset is not allocatable in its current BAM status."
        if asset.allocation_hold:
            return "Preferred asset is on allocation hold."
        if not asset.automatic_allocation_enabled:
            return "Preferred asset requires manual allocation."
        stock_custodian = get_bam_default_custodian()
        if asset.current_custodian_id and (
            stock_custodian is None or asset.current_custodian_id != stock_custodian.pk
        ):
            return "Preferred asset is currently in non-stock custody."
        if asset_reservation_conflicts(
            asset=asset,
            requested_start=item.request.requested_start,
            requested_end=item.request.requested_end,
            exclude_item_id=item.pk,
        ).exists():
            return "Preferred asset has a conflicting reservation or active checkout."
        return "Preferred asset is eligible now; BAM will retry this queue entry on the next automation pulse."

    if eligible_assets_for_item(item, respect_automation_policy=True).exists():
        return "A suitable asset is eligible now; BAM will retry this queue entry on the next automation pulse."
    return "No automatically eligible asset is currently available for this request window."


def process_due_bam_automation(*, fallback_actor=None):
    """Run one idempotent automation pulse for scheduled/launcher execution."""
    settings_obj = get_bam_automation_settings()
    actor = get_bam_automation_actor(fallback_actor) if fallback_actor is not None else (
        settings_obj.automation_actor or settings_obj.default_custodian or get_bam_default_custodian()
    )
    if actor is None:
        return {"processed": 0, "allocated": 0, "waitlisted": 0, "checked_out": 0, "skipped": 0}

    counts = {
        "processed": 0,
        "allocated": 0,
        "promoted": 0,
        "waitlisted": 0,
        "checked_out": 0,
        "skipped": 0,
    }

    if settings_obj.auto_approve_available_requests:
        pending_ids = list(
            AssetRequestItem.objects.filter(
                status=AssetRequestItem.Status.PENDING,
                request__status__in=[
                    AssetRequest.Status.SUBMITTED,
                    AssetRequest.Status.QUEUED,
                    AssetRequest.Status.PARTIALLY_RESERVED,
                ],
            ).values_list("pk", flat=True)
        )
        for item_id in pending_ids:
            item = AssetRequestItem.objects.get(pk=item_id)
            try:
                result = auto_process_request_item(item=item, fallback_actor=actor)
            except ValidationError:
                counts["skipped"] += 1
                continue
            counts["processed"] += 1
            result.refresh_from_db()
            if result.status == AssetRequestItem.Status.CHECKED_OUT:
                counts["checked_out"] += 1
            elif result.status == AssetRequestItem.Status.ALLOCATED:
                counts["allocated"] += 1
            elif result.status == AssetRequestItem.Status.WAITLISTED:
                counts["waitlisted"] += 1

    # WAITLISTED is not terminal. A request may have entered the queue while
    # an asset was checked out, on hold, under repair, or otherwise ineligible.
    # Reconsider queued work on every automation pulse so a resource that became
    # free through a manual stock/custody/status change cannot leave queue #1
    # stranded indefinitely.
    if settings_obj.auto_promote_waitlist:
        today = timezone.localdate()
        waitlisted_ids = list(
            AssetRequestItem.objects.filter(
                status=AssetRequestItem.Status.WAITLISTED,
                request__requested_end__gte=today,
                request__status__in=[
                    AssetRequest.Status.QUEUED,
                    AssetRequest.Status.PARTIALLY_RESERVED,
                    AssetRequest.Status.SUBMITTED,
                ],
            )
            .order_by(
                "request__requested_start",
                "request__created_at",
                "created_at",
                "pk",
            )
            .values_list("pk", flat=True)
        )
        for item_id in waitlisted_ids:
            item = AssetRequestItem.objects.select_related(
                "request", "preferred_asset", "preferred_asset__status",
                "department", "asset_type",
            ).get(pk=item_id)
            try:
                result = allocate_request_item(
                    item=item,
                    actor=actor,
                    allow_equivalent=settings_obj.allow_equivalent_substitution,
                    automated=True,
                )
            except ValidationError:
                counts["skipped"] += 1
                continue
            if result.status == AssetRequestItem.Status.ALLOCATED:
                counts["processed"] += 1
                counts["allocated"] += 1
                counts["promoted"] += 1

    if settings_obj.auto_transfer_on_approval:
        today = timezone.localdate()
        allocated_ids = list(
            AssetRequestItem.objects.filter(
                status=AssetRequestItem.Status.ALLOCATED,
                request__requested_start__lte=today,
                request__requested_end__gte=today,
            ).values_list("pk", flat=True)
        )
        for item_id in allocated_ids:
            item = AssetRequestItem.objects.select_related("allocated_asset").get(pk=item_id)
            try:
                issue_checkout(
                    item=item,
                    actor=actor,
                    notes="Automatic BAM scheduled checkout",
                    automated=True,
                )
            except ValidationError:
                counts["skipped"] += 1
                continue
            counts["processed"] += 1
            counts["checked_out"] += 1

    return counts
