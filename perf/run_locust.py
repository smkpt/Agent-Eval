"""Automated Headless Locust Runner with Managed FastAPI Uvicorn Process."""
import sys
import os
import time
import subprocess
import urllib.request
import urllib.error

def wait_for_server(url: str, timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LocustHealthProbe"})
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def run_headless_locust(
    users: int = 10,
    spawn_rate: int = 5,
    run_time_seconds: int = 5,
    host: str = "http://127.0.0.1:8000"
) -> bool:
    print("======================================================================")
    print(f"  STARTING MANAGED FASTAPI APP & HEADLESS LOCUST LOAD TEST")
    print(f"  Target: {host} ({users} VUs, {spawn_rate}/s, duration: {run_time_seconds}s)")
    print("======================================================================")

    try:
        import uvicorn
        import locust
    except ImportError as exc:
        print(f"[SKIP] Locust/Uvicorn not installed in local environment ({exc}).")
        print("       In CI/CD environments, 'pip install -r requirements.txt' installs full stack.")
        return True

    server_proc = None
    try:
        # 1. Start Uvicorn as an independent background process
        print("Spawning Uvicorn server process...")
        server_cmd = [
            sys.executable, "-m", "uvicorn",
            "src.api.app:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-level", "warning"
        ]
        server_proc = subprocess.Popen(server_cmd)

        # 2. Wait for server readiness
        print(f"Waiting for {host}/health probe...")
        ready = wait_for_server(f"{host}/health", timeout=15)
        if not ready:
            print("ERROR: FastAPI server failed to become ready within timeout.")
            return False
        print("FastAPI server is UP and healthy!")

        # 3. Setup reporting directory
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        csv_prefix = os.path.join(reports_dir, "locust_benchmark")
        html_report = os.path.join(reports_dir, "locust_report.html")

        # 4. Run Locust Headless
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

        print("Running command:", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(res.stdout)
        if res.stderr:
            print("Locust Stderr:", res.stderr)

        print("======================================================================")
        print(f"  LOCUST RUN COMPLETED WITH EXIT CODE: {res.returncode}")
        print("======================================================================")
        return res.returncode == 0

    finally:
        if server_proc:
            print("Terminating Uvicorn background process...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("Uvicorn process cleanly terminated.")

if __name__ == "__main__":
    success = run_headless_locust()
    sys.exit(0 if success else 1)
