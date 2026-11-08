"""Read-only production DNS/HTTPS inspection. No credentials or DNS writes.

    python scripts/check_production_network.py --expect-ip 8.210.9.172 --report dns-report.json

The expectation is historical evidence, not a replacement for live DNS facts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path


def inspect(hosts: list[str], pages: list[str], timeout: int = 12) -> dict:
    result = {"checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "dns": {}, "https": {}}
    for host in hosts:
        try:
            info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            result["dns"][host] = {"status": "PASS",
                                   "addresses": sorted({rec[4][0] for rec in info})}
        except OSError as exc:
            result["dns"][host] = {"status": "UNVERIFIED", "error": str(exc)}
    for url in pages:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SkyED-Homework-Audit/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                sample = r.read(1024)
                status = r.status
                result["https"][url] = {
                    "status": "PASS" if status == 200 and sample else "FAIL",
                    "http_status": status, "final_url": r.url,
                    "content_type": r.headers.get("Content-Type", "")}
        except Exception as exc:
            result["https"][url] = {"status": "UNVERIFIED", "error": str(exc)}
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expect-ip", default="", help="Optional historical IP for mismatch alert")
    ap.add_argument("--report", type=Path, default=Path("skyed-network-report.json"))
    args = ap.parse_args()
    r = inspect(["skyed.org", "www.skyed.org"],
                ["https://skyed.org/", "https://skyed.org/en/lesson181/",
                 "https://skyed.org/en/lesson182/"])
    if args.expect_ip:
        r["expected_ip"] = args.expect_ip
        for item in r["dns"].values():
            if item["status"] == "PASS" and args.expect_ip not in item["addresses"]:
                item["status"] = "MISMATCH"
    r["overall"] = "PASS" if all(i["status"] == "PASS" for i in list(r["dns"].values()) + list(r["https"].values())) else "REQUIRES_REVIEW"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r["overall"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
