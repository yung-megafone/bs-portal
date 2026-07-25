from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Punch, PunchCorrection, TimeclockEvent


@dataclass(frozen=True)
class ClockState:
    is_clocked_in: bool
    last_punch: Punch | None


def _latest_effective_punch(employee):
    """
    Return the last punch by effective time.

    Corrections may alter timestamps, so state is derived from immutable punch
    history plus correction records rather than a mutable employee flag.
    """
    punches = list(
        Punch.objects.filter(employee=employee)
        .prefetch_related("corrections")
        .order_by("occurred_at", "created_at")
    )
    if not punches:
        return None
    return max(
        punches,
        key=lambda punch: (punch.effective_occurred_at, punch.created_at),
    )


def get_clock_state(employee):
    last_punch = _latest_effective_punch(employee)
    return ClockState(
        is_clocked_in=(
            last_punch is not None
            and last_punch.effective_punch_type == Punch.PunchType.IN
        ),
        last_punch=last_punch,
    )


def _record_event(*, employee, actor, event_type, punch, summary, metadata=None):
    return TimeclockEvent.objects.create(
        employee=employee,
        actor=actor,
        event_type=event_type,
        punch=punch,
        summary=summary,
        metadata=metadata or {},
    )


def clock_in(*, employee, actor):
    if employee.pk != actor.pk:
        raise PermissionDenied("Users may only clock themselves in.")

    User = get_user_model()
    with transaction.atomic():
        # Serialize concurrent punch requests for this employee.
        locked_employee = User.objects.select_for_update().get(pk=employee.pk)
        state = get_clock_state(locked_employee)
        if state.is_clocked_in:
            raise ValidationError("You are already clocked in.")

        occurred_at = timezone.now()
        punch = Punch.objects.create(
            employee=locked_employee,
            punch_type=Punch.PunchType.IN,
            occurred_at=occurred_at,
            recorded_by=actor,
            source=Punch.Source.PORTAL,
        )
        _record_event(
            employee=locked_employee,
            actor=actor,
            event_type=TimeclockEvent.EventType.CLOCK_IN,
            punch=punch,
            summary="Clocked in through B.S. Portal.",
            metadata={"source": Punch.Source.PORTAL},
        )
        return punch


def clock_out(*, employee, actor):
    if employee.pk != actor.pk:
        raise PermissionDenied("Users may only clock themselves out.")

    User = get_user_model()
    with transaction.atomic():
        locked_employee = User.objects.select_for_update().get(pk=employee.pk)
        state = get_clock_state(locked_employee)
        if not state.is_clocked_in:
            raise ValidationError("You are already clocked out.")

        occurred_at = timezone.now()
        punch = Punch.objects.create(
            employee=locked_employee,
            punch_type=Punch.PunchType.OUT,
            occurred_at=occurred_at,
            recorded_by=actor,
            source=Punch.Source.PORTAL,
        )
        _record_event(
            employee=locked_employee,
            actor=actor,
            event_type=TimeclockEvent.EventType.CLOCK_OUT,
            punch=punch,
            summary="Clocked out through B.S. Portal.",
            metadata={"source": Punch.Source.PORTAL},
        )
        return punch


def correct_punch(
    *,
    punch,
    actor,
    corrected_punch_type,
    corrected_occurred_at,
    reason,
):
    """
    Append an administrative correction without modifying the original punch.
    """
    if not actor.is_staff:
        raise PermissionDenied("Only authorized administrators may correct punches.")

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A correction reason is required.")

    if corrected_punch_type not in Punch.PunchType.values:
        raise ValidationError("Invalid corrected punch type.")

    with transaction.atomic():
        locked_punch = Punch.objects.select_for_update().select_related(
            "employee"
        ).get(pk=punch.pk)

        correction = PunchCorrection.objects.create(
            punch=locked_punch,
            corrected_punch_type=corrected_punch_type,
            corrected_occurred_at=corrected_occurred_at,
            reason=reason,
            corrected_by=actor,
        )

        _record_event(
            employee=locked_punch.employee,
            actor=actor,
            event_type=TimeclockEvent.EventType.CORRECTION,
            punch=locked_punch,
            summary="Administrative punch correction recorded.",
            metadata={
                "original_type": locked_punch.punch_type,
                "original_occurred_at": locked_punch.occurred_at.isoformat(),
                "corrected_type": corrected_punch_type,
                "corrected_occurred_at": corrected_occurred_at.isoformat(),
                "reason": reason,
                "correction_id": str(correction.pk),
            },
        )
        return correction
