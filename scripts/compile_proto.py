"""
compile_proto.py — PlatformIO pre-build script.

Compiles proto/telemetry.proto into C sources using the Nanopb generator.
Output:
    src/generated/telemetry.pb.c
    include/generated/telemetry.pb.h

The Nanopb generator is located inside the Nanopb library installed by
PlatformIO.  This script finds it automatically via the library manager.

Skip conditions:
  - Set SKIP_PROTO_BUILD=1 to bypass when iterating on non-proto changes.
  - Skips regeneration when .proto/.options are older than the generated files.
"""

Import("env")  # noqa: F821  — PlatformIO injects this

import os
import sys
import glob
import subprocess

PROJECT_DIR = env["PROJECT_DIR"]  # noqa: F821
PROTO_DIR   = os.path.join(PROJECT_DIR, "proto")
PROTO_FILE  = os.path.join(PROTO_DIR, "telemetry.proto")
OPTIONS_FILE = os.path.join(PROTO_DIR, "telemetry.options")
OUT_C       = os.path.join(PROJECT_DIR, "src", "generated", "telemetry.pb.c")
OUT_H       = os.path.join(PROJECT_DIR, "include", "generated", "telemetry.pb.h")
SKIP_VAR    = "SKIP_PROTO_BUILD"


def _find_nanopb_generator() -> str | None:
    """Locate the nanopb_generator.py inside the PlatformIO Nanopb library."""
    # PlatformIO stores libs under .pio/libdeps/<env>/Nanopb/generator/
    libdeps = os.path.join(PROJECT_DIR, ".pio", "libdeps")
    if not os.path.isdir(libdeps):
        return None
    # Search all environments
    for pattern in [
        os.path.join(libdeps, "*", "Nanopb", "generator", "nanopb_generator.py"),
        os.path.join(libdeps, "*", "nanopb", "generator", "nanopb_generator.py"),
    ]:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def _needs_rebuild() -> bool:
    """Return True if the generated files are missing or older than sources."""
    if not os.path.exists(OUT_C) or not os.path.exists(OUT_H):
        return True
    out_mtime = min(os.path.getmtime(OUT_C), os.path.getmtime(OUT_H))
    for src in [PROTO_FILE, OPTIONS_FILE]:
        if os.path.exists(src) and os.path.getmtime(src) > out_mtime:
            return True
    return False


def _ensure_protobuf() -> None:
    """Install google.protobuf if it is not already available.

    nanopb_generator.py imports google.protobuf to parse .proto files.
    PlatformIO runs build scripts in its own Python environment, which may
    not have the package pre-installed.  We install it silently on first
    use and it persists for subsequent builds.
    """
    try:
        import google.protobuf  # noqa: F401
        return  # already installed
    except ImportError:
        pass

    print("[compile_proto] Installing google.protobuf (required by nanopb_generator)…")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "protobuf"],
        check=False,
    )
    if result.returncode != 0:
        print("[compile_proto] ERROR: failed to install 'protobuf' via pip. "
              "Run: pip install protobuf", file=sys.stderr)
        env.Exit(1)  # noqa: F821


def compile_proto() -> None:
    if os.environ.get(SKIP_VAR):
        print(f"[compile_proto] {SKIP_VAR} is set — skipping")
        return

    if not os.path.exists(PROTO_FILE):
        print(f"[compile_proto] WARNING: {PROTO_FILE} not found — skipping",
              file=sys.stderr)
        return

    if not _needs_rebuild():
        print("[compile_proto] Generated files are up to date — skipping")
        return

    _ensure_protobuf()

    generator = _find_nanopb_generator()
    if generator is None:
        print("[compile_proto] ERROR: nanopb_generator.py not found. "
              "Run 'pio pkg install' first to download the Nanopb library.",
              file=sys.stderr)
        env.Exit(1)  # noqa: F821

    # Ensure output directories exist.
    os.makedirs(os.path.dirname(OUT_C), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_H), exist_ok=True)

    # The Nanopb generator produces .pb.c and .pb.h next to the .proto file
    # by default.  We use -D to redirect output, then move files to their
    # final locations.
    #
    # nanopb_generator.py expects the options file to be alongside the proto
    # file with the same base name, which is already the case
    # (proto/telemetry.options for proto/telemetry.proto).

    # Generate into a temp dir and then move to final locations
    tmp_dir = os.path.join(PROJECT_DIR, "proto", "_gen")
    os.makedirs(tmp_dir, exist_ok=True)

    cmd = [
        sys.executable, generator,
        "-I", PROTO_DIR,
        "-D", tmp_dir,
        PROTO_FILE,
    ]

    print(f"[compile_proto] $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print(f"[compile_proto] ERROR: nanopb_generator exited with code {result.returncode}",
              file=sys.stderr)
        env.Exit(1)  # noqa: F821

    # Move generated files to their final locations.
    import shutil
    tmp_c = os.path.join(tmp_dir, "telemetry.pb.c")
    tmp_h = os.path.join(tmp_dir, "telemetry.pb.h")

    if os.path.exists(tmp_c):
        shutil.move(tmp_c, OUT_C)
    if os.path.exists(tmp_h):
        shutil.move(tmp_h, OUT_H)

    # Clean up temp dir
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"[compile_proto] Generated {OUT_C}")
    print(f"[compile_proto] Generated {OUT_H}")


compile_proto()
