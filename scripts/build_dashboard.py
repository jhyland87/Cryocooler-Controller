"""
build_dashboard.py — PlatformIO pre-build script.

Builds the Preact/TypeScript SPA dashboard located in dashboard/ and writes
the compiled output (index.html, app.js, style.css) into data/ so that
embed_web.py can subsequently embed them into web_content.h.

Build steps:
  1.  cd dashboard/
  2.  npm ci   (or npm install if node_modules is absent / package-lock is stale)
  3.  npm run build   (vite build → outputs to data/)

Requirements:
  - Node.js and npm must be on the system PATH.
  - The dashboard/ directory must exist at the project root.

Skip conditions:
  - Set the environment variable SKIP_DASHBOARD_BUILD=1 to bypass this script
    when iterating on firmware-only changes.
"""

Import("env")  # noqa: F821  — PlatformIO injects this

import os
import subprocess
import sys

PROJECT_DIR    = env["PROJECT_DIR"]              # noqa: F821
DASHBOARD_DIR  = os.path.join(PROJECT_DIR, "dashboard")
SKIP_VAR       = "SKIP_DASHBOARD_BUILD"


def _run(cmd: list[str], cwd: str) -> None:
    """Run *cmd* in *cwd*, streaming output.  Aborts the build on failure."""
    print(f"[build_dashboard] $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"[build_dashboard] ERROR: command exited with code {result.returncode}",
              file=sys.stderr)
        env.Exit(1)


def _npm_executable() -> str:
    """Return 'npm.cmd' on Windows, 'npm' elsewhere."""
    return "npm.cmd" if sys.platform == "win32" else "npm"


def build_dashboard() -> None:
    # Allow developers to skip the dashboard build for faster firmware iteration.
    if os.environ.get(SKIP_DASHBOARD_BUILD := SKIP_VAR):
        print(f"[build_dashboard] {SKIP_VAR} is set — skipping dashboard build")
        return

    if not os.path.isdir(DASHBOARD_DIR):
        print(f"[build_dashboard] WARNING: {DASHBOARD_DIR} not found — skipping",
              file=sys.stderr)
        return

    npm = _npm_executable()

    # Use 'ci' when a lockfile is present for reproducible installs; fall back
    # to 'install' if package-lock.json is missing (e.g. first checkout).
    lockfile = os.path.join(DASHBOARD_DIR, "package-lock.json")
    install_cmd = [npm, "ci"] if os.path.exists(lockfile) else [npm, "install"]

    print("[build_dashboard] Installing dashboard dependencies…")
    _run(install_cmd, DASHBOARD_DIR)

    print("[build_dashboard] Building dashboard…")
    _run([npm, "run", "build"], DASHBOARD_DIR)

    print("[build_dashboard] Dashboard build complete.")


build_dashboard()
