import os
import gzip
import json
import tempfile
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a PostgreSQL dump, gzip it, send to Telegram, then remove local duplicates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retain",
            type=int,
            default=1,
            help="How many recent backup files to retain (default: 1)",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=os.path.join(tempfile.gettempdir(), "db_backups"),
            help="Directory to store temporary backup files before upload",
        )

    def handle(self, *args, **options):
        # Telegram env compatibility: prefer Django settings, fallback to common env names
        bot_token = (
            os.environ.get("TELEGRAM_BOT_TOKEN")
            or os.environ.get("TG_LOG_TOKEN")
            or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        )
        chat_id = (
            os.environ.get("TELEGRAM_CHAT_ID")
            or os.environ.get("TG_LOG_CHAT_ID")
            or getattr(settings, "TELEGRAM_CHAT_ID", "")
        )

        if not bot_token or not chat_id:
            raise CommandError(
                "Telegram credentials missing. Set TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (or TG_LOG_TOKEN/TG_LOG_CHAT_ID)."
            )

        # Database config: prefer Django settings, fallback to environment
        db = settings.DATABASES.get("default", {})
        engine = (db.get("ENGINE") or "").split(".")[-1]
        if engine and engine != "postgresql":
            raise CommandError("This backup command only supports PostgreSQL.")

        db_name = db.get("NAME") or os.environ.get("DB_NAME")
        db_user = db.get("USER") or os.environ.get("DB_USER")
        db_password = db.get("PASSWORD") or os.environ.get("DB_PASSWORD")
        db_host = db.get("HOST") or os.environ.get("DB_HOST") or "localhost"
        db_port = str(db.get("PORT") or os.environ.get("DB_PORT") or "5432")

        if not all([db_name, db_user]):
            raise CommandError("Database NAME and USER must be configured.")

        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        # Timestamp (Asia/Tashkent like earlier behavior isn't strictly required here)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        base_filename = f"postgres_{db_name}_{timestamp}.sql"
        sql_path = os.path.join(output_dir, base_filename)
        gz_path = sql_path + ".gz"

        # Build pg_dump command (read-only; does not modify DB)
        dump_cmd = [
            "pg_dump",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "--format=plain",
            "--no-owner",
            "--no-privileges",
        ]

        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password

        # Execute dump
        try:
            with open(sql_path, "wb") as f:
                proc = subprocess.run(
                    dump_cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    check=False,
                )
            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="replace")
                raise CommandError(f"pg_dump failed (code {proc.returncode}):\n{stderr}")
        except FileNotFoundError:
            raise CommandError(
                "pg_dump not found. Install PostgreSQL client tools and ensure pg_dump is in PATH."
            )

        # Gzip
        try:
            with open(sql_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                while True:
                    chunk = f_in.read(1024 * 1024)
                    if not chunk:
                        break
                    f_out.write(chunk)
        finally:
            try:
                os.remove(sql_path)
            except Exception:
                pass

        # Send to Telegram
        caption = f"Daily DB backup for {db_name} at {timestamp}"
        api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

        try:
            import requests  # pylint: disable=import-outside-toplevel
        except Exception as exc:
            raise CommandError(f"'requests' is required. Install it in requirements.txt. Error: {exc}")

        with open(gz_path, "rb") as fh:
            files = {"document": (os.path.basename(gz_path), fh, "application/gzip")}
            data = {"chat_id": chat_id, "caption": caption}
            resp = requests.post(api_url, data=data, files=files, timeout=120)

        if resp.status_code != 200:
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
            raise CommandError(
                f"Telegram upload failed: HTTP {resp.status_code} -> {json.dumps(payload)[:500]}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Backup uploaded to Telegram: {os.path.basename(gz_path)}"
        ))

        # Retention (remove duplicates/old backups)
        try:
            retain = int(options["retain"]) if options["retain"] else 1
        except Exception:
            retain = 1

        try:
            backups = [
                os.path.join(output_dir, fname)
                for fname in os.listdir(output_dir)
                if fname.endswith(".sql.gz") and fname.startswith(f"postgres_{db_name}_")
            ]
            backups.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for old in backups[retain:]:
                try:
                    os.remove(old)
                except Exception:
                    pass
        except Exception:
            pass


