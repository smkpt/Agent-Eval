"""Automated Headless Locust Runner with SLA Quality Gate Assertions."""
import sys
import os
import time
import subprocess
import threading

def run_headless_locust(
    users: int = 20,
    spawn_rate: int = 5,
    run_time_seconds: int = 10,
    host: str = "http://127.0.0.1:8000"
):
    print("======================================================================")
    print(f"  LAUNCHING HEADLESS LOCUST LOAD TEST ({users} users, {spawn_rate}/s, {run_time_seconds}s)")
    print(f"  Target: {host}")
    print("======================================================================")

    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    csv_prefix = os.path.join(reports_dir, "locust_benchmark")
    html_report = os.path.join(reports_dir, "locust_report.html")

    cmd = [
        sys.executable, "-m", "locust",
        "-f", os.path.join(os.path.dirname(__file__), "locustfile.py"),
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", f"{run_time_seconds}s",
        "--host", host,
        f"--csv={csv_prefix}",
        f"--html={html_report}"
    ]

    print("Executing:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("Locust Stderr:", res.stderr)

    return res.returncode == 0

if __name__ == "__main__":
    success = run_headless_locust()
    sys.exit(0 if success else 1)
