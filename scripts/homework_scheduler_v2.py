"""Safe, idempotent scheduler for SkyED homework publishing.

The scheduler invokes an existing, explicitly configured publishing command.
It does not contain WordPress credentials or bypass the existing pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def run(config_path: Path, database_path: Path, *, execute: bool = False) -> list[dict]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    timezone = ZoneInfo(config.get("timezone", "Asia/Shanghai"))
    now = datetime.now(timezone)
    results: list[dict] = []
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path, timeout=30) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS publications (
            job_id TEXT NOT NULL, local_date TEXT NOT NULL,
            published_at TEXT NOT NULL, PRIMARY KEY(job_id, local_date)
        )""")
        for job in config.get("jobs", []):
            job_id = str(job["id"])
            weekdays = job.get("weekdays", [0, 1, 2, 3, 4])
            hour, minute = map(int, job["time"].split(":"))
            due = now.weekday() in weekdays and (now.hour, now.minute) >= (hour, minute)
            published = db.execute(
                "SELECT 1 FROM publications WHERE job_id=? AND local_date=?",
                (job_id, now.date().isoformat()),
            ).fetchone()
            if not due or published:
                continue
            if not execute:
                results.append({"id": job_id, "status": "due_dry_run"})
                continue
            command = job.get("command")
            if not isinstance(command, list) or not command or not all(
                isinstance(item, str) and item for item in command
            ):
                raise ValueError(f"Job {job_id}: command must be a nonempty argv list")
            # Transaction held during publication to prevent competing invocations.
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM publications WHERE job_id=? AND local_date=?",
                (job_id, now.date().isoformat()),
            ).fetchone():
                db.rollback()
                continue
            env = os.environ.copy()
            env["SKYED_HOMEWORK_JOB_ID"] = job_id
            env["SKYED_HOMEWORK_DATE"] = now.date().isoformat()
            try:
                subprocess.run(command, check=True, env=env, timeout=300)
            except Exception:
                db.rollback()
                raise
            db.execute(
                "INSERT INTO publications VALUES (?, ?, ?)",
                (job_id, now.date().isoformat(), now.isoformat()),
            )
            db.commit()
            results.append({"id": job_id, "status": "published"})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run due SkyED homework jobs")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("var/homework-scheduler.sqlite3"))
    parser.add_argument("--execute", action="store_true", help="Enable actual publishing")
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.database, execute=args.execute), indent=2))


if __name__ == "__main__":
    main()
