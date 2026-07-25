from __future__ import annotations

import hashlib
import mimetypes
import re
import secrets
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Asset, AssetCustody, AssetEvent, AssetEvidence

MAX_ID_ATTEMPTS = 65536
HEX_RE = re.compile(r"^[0-9A-F]{4}$")


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


def update_asset_details(*, asset, actor, ownership, manufacturer, model, serial_number, acquired_at, notes):
    before = {
        "ownership": asset.ownership,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "acquired_at": asset.acquired_at.isoformat() if asset.acquired_at else None,
        "notes": asset.notes,
    }
    with transaction.atomic():
        asset.ownership = ownership
        asset.manufacturer = (manufacturer or "").strip()
        asset.model = (model or "").strip()
        asset.serial_number = (serial_number or "").strip()
        asset.acquired_at = acquired_at
        asset.notes = (notes or "").strip()
        asset.save()
        after = {
            "ownership": asset.ownership,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "acquired_at": asset.acquired_at.isoformat() if asset.acquired_at else None,
            "notes": asset.notes,
        }
        _event(asset, actor, AssetEvent.EventType.UPDATED, "Asset details updated.", {"before": before, "after": after})
    return asset
