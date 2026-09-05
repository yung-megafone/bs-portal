# Timeclock Guide — v0.2.0-alpha

The Timeclock module provides a small append-oriented punch system inside B.S. Portal.

## User workflow

Open **Timeclock**. The page shows your current effective state and up to 50 recent punches.

### Clock in

Select **Clock in** when currently clocked out. BSP creates an immutable `IN` Punch with the current server time and records a Timeclock event.

### Clock out

Select **Clock out** when currently clocked in. BSP creates an immutable `OUT` Punch and event.

### Invalid duplicate state

BSP rejects:

- clocking in when already clocked in;
- clocking out when already clocked out.

Users may only punch themselves through the current UI/service.

## Immutable punches and corrections

A Punch row is not edited to “fix” time. Staff users use the correction workflow, which appends a `PunchCorrection` containing:

- corrected punch type;
- corrected occurred-at timestamp;
- required reason;
- correcting user;
- correction timestamp.

Multiple corrections are allowed. The latest correction becomes effective while the original Punch and earlier corrections remain available.

## Effective clock state

Clock state is derived from the latest punch by **effective** timestamp/type, meaning corrections can change which punch is logically last. BSP does not maintain a mutable `is_clocked_in` flag on the user.

## Permissions

- ordinary users: view/punch themselves;
- staff: may correct punches;
- corrections require a reason.

## Audit/event history

Timeclock event types:

- Clocked in;
- Clocked out;
- Punch corrected.

Correction event metadata contains original and corrected values.

## Limitations

The current Timeclock is an internal punch record, not a payroll engine. Scheduling, payroll calculations, manager approvals, time-off, wage rules, and payroll export are not implemented in v0.2.0-alpha.
