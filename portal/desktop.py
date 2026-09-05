"""B.S. Portal packaged Windows launcher.

Default mode starts a localhost Waitress server, runs one BAM automation pulse,
opens the browser, and keeps a small system-tray controller alive. Maintenance
modes are used by the installer for backups, migrations, and health checks.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from config.desktop_runtime import (
    RuntimeConfigurationError,
    configure_environment,
    default_data_dir,
)


LOGGER = logging.getLogger("bs_portal.desktop")


def show_error(title: str, message: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        if sys.stderr is not None:
            sys.stderr.write(f"{title}: {message}\n")


def wait_for_tcp(host: str, port: int, *, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.35)
    return False


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def existing_instance_is_bsp(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health/", timeout=1.25) as response:
            return response.status == 200 and b'"status": "ok"' in response.read(256)
    except (OSError, urllib.error.URLError, ValueError):
        return False


def ensure_mysql_service(config: dict) -> None:
    mysql = config["mysql"]
    service_name = str(mysql.get("service_name", "BSPortalMySQL"))

    query = subprocess.run(
        ["sc.exe", "query", service_name],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if query.returncode != 0:
        raise RuntimeConfigurationError(
            f"The {service_name} database service is not installed. Run B.S. Portal Setup again and choose Repair."
        )

    output = (query.stdout or "").upper()
    if "RUNNING" not in output:
        start = subprocess.run(
            ["sc.exe", "start", service_name],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if start.returncode not in (0, 1056):
            raise RuntimeConfigurationError(
                f"The {service_name} service is stopped and could not be started. "
                "Run B.S. Portal Setup as Administrator and choose Repair."
            )

    database = config["database"]
    if not wait_for_tcp(str(database["host"]), int(database["port"]), timeout=25.0):
        raise RuntimeConfigurationError(
            f"MySQL did not become ready on {database['host']}:{database['port']}."
        )


def setup_django(config: dict) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")
    os.environ["BS_PORTAL_SERVER_PORT"] = str(config["server"].get("port", 8765))

    import django

    django.setup()


def backup_database(config: dict) -> Path:
    # Installer-oriented backup: database only. User-initiated portable exports
    # default to including uploaded media, but release migrations do not mutate
    # MEDIA_ROOT and therefore do not need to duplicate potentially large files.
    from apps.core.database_backups import create_portable_backup

    return create_portable_backup(include_media=False)


def run_maintenance(config: dict, action: str) -> int:
    ensure_mysql_service(config)
    setup_django(config)

    from django.core.management import call_command

    if action == "check":
        call_command("check", verbosity=1)
        return 0

    if action == "backup":
        path = backup_database(config)
        LOGGER.info("Database backup created: %s", path)
        return 0

    if action == "backup-and-migrate":
        path = backup_database(config)
        LOGGER.info("Pre-migration database backup created: %s", path)
        call_command("migrate", interactive=False, verbosity=1)
        call_command("check", verbosity=1)
        return 0

    raise RuntimeConfigurationError(f"Unknown maintenance action: {action}")


def has_pending_migrations() -> bool:
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return bool(executor.migration_plan(targets))


def initial_url(host: str, port: int) -> str:
    from django.contrib.auth import get_user_model

    path = "/" if get_user_model().objects.exists() else "/setup/"
    return f"http://{host}:{port}{path}"


def run_automation_pulse() -> None:
    from django.core.management import call_command

    try:
        call_command("process_bam_automation", verbosity=0)
    except Exception:
        LOGGER.exception("BAM automation startup pulse failed")


def build_tray_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (64, 64), "#0b1118")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=10, fill="#16212d", outline="#4e9cff", width=3)
    draw.text((14, 20), "BS", fill="#ffffff")
    return image


def run_server(config: dict, *, no_browser: bool = False) -> int:
    ensure_mysql_service(config)
    setup_django(config)

    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from waitress.server import create_server

    call_command("check", verbosity=0)
    if has_pending_migrations():
        raise RuntimeConfigurationError(
            "The database has pending migrations. Run the current B.S. Portal installer again so it can back up and migrate the database."
        )

    run_automation_pulse()

    host = str(config["server"].get("host", "127.0.0.1"))
    port = int(config["server"].get("port", 8765))
    url = initial_url(host, port)

    if port_is_open(host, port):
        if not existing_instance_is_bsp(host, port):
            raise RuntimeConfigurationError(
                f"Port {port} is already in use by another application. Change the B.S. Portal desktop port or stop the conflicting process."
            )
        if not no_browser:
            webbrowser.open(url)
        return 0

    application = get_wsgi_application()
    server = create_server(application, host=host, port=port, threads=8)
    server_thread = threading.Thread(target=server.run, name="BS-Portal-WSGI", daemon=True)
    server_thread.start()

    if not wait_for_tcp(host, port, timeout=15.0):
        raise RuntimeConfigurationError(f"B.S. Portal did not start on {host}:{port}.")

    if not no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        import pystray

        def open_portal(_icon=None, _item=None):
            webbrowser.open(initial_url(host, port))

        def open_logs(_icon=None, _item=None):
            os.startfile(str(default_data_dir() / "logs"))  # type: ignore[attr-defined]

        def open_backup_restore(_icon=None, _item=None):
            webbrowser.open(f"http://{host}:{port}/data/")

        def quit_portal(icon, _item=None):
            try:
                server.close()
            finally:
                icon.stop()

        tray = pystray.Icon(
            "BS-Portal",
            build_tray_image(),
            "B.S. Portal",
            menu=pystray.Menu(
                pystray.MenuItem("Open B.S. Portal", open_portal, default=True),
                pystray.MenuItem("Backup & restore", open_backup_restore),
                pystray.MenuItem("View logs", open_logs),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", quit_portal),
            ),
        )
        tray.run()
    except Exception:
        LOGGER.exception("System tray failed; keeping the server alive without a tray icon")
        try:
            while server_thread.is_alive():
                server_thread.join(timeout=1.0)
        except KeyboardInterrupt:
            server.close()

    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B.S. Portal Windows desktop runtime")
    parser.add_argument(
        "--maintenance",
        choices=["check", "backup", "backup-and-migrate"],
        help="run an installer/maintenance operation and exit",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        config = configure_environment()
        if args.maintenance:
            return run_maintenance(config, args.maintenance)
        return run_server(config, no_browser=args.no_browser)
    except Exception as exc:
        LOGGER.exception("B.S. Portal startup failed")
        show_error("B.S. Portal", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
