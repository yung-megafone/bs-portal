# Local Development

The codebase is Linux-oriented but Windows-friendly.

## Windows
Use Python 3.11 and PowerShell. Avoid globally installing project packages; use `.venv`.

## Linux
Use Python 3.11 and a virtual environment.

## MySQL/InnoDB
B.S. Portal intentionally uses MySQL/InnoDB as the application database rather than silently falling back to SQLite. This reduces environment drift in database behavior.
