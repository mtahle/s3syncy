"""CLI entry-point for s3sync.

Usage:
  s3sync start          [-c config.yaml] [--background]
  s3sync stop|pause|resume|reload [-c config.yaml]
  s3sync daemon-status  [-c config.yaml]
  s3sync search         [-c config.yaml] QUERY
  s3sync ls             [-c config.yaml] PATH
  s3sync pull           [-c config.yaml] REL DEST
  s3sync status         [-c config.yaml]
  s3sync init
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__


def _config_path(args) -> Path:
    return Path(args.config).resolve()


def _pid_file_path(args, config_path: Path) -> Path:
    if getattr(args, "pid_file", None):
        return Path(args.pid_file).resolve()
    return config_path.with_suffix(config_path.suffix + ".pid")


def _state_file_path(args, config_path: Path) -> Path:
    if getattr(args, "state_file", None):
        return Path(args.state_file).resolve()
    return config_path.with_suffix(config_path.suffix + ".state.json")


def _read_pid_file(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        if raw.startswith("{"):
            payload = json.loads(raw)
            return int(payload.get("pid", 0)) or None
        return int(raw)
    except Exception:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _send_signal(args, sig: int, action: str) -> None:
    config_path = _config_path(args)
    pid_file = _pid_file_path(args, config_path)
    pid = _read_pid_file(pid_file)
    if not pid:
        print(f"No daemon PID file found at {pid_file}", file=sys.stderr)
        sys.exit(1)
    if not _process_alive(pid):
        print(f"Stale PID file ({pid_file}); process {pid} is not running", file=sys.stderr)
        sys.exit(1)

    try:
        os.kill(pid, sig)
    except OSError as exc:
        print(f"Failed to send {action} signal to pid {pid}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Sent {action} signal to pid {pid}")


# -- subcommands -----------------------------------------------------------


def cmd_start(args) -> None:
    from .daemon import SyncDaemon

    config_path = _config_path(args)
    pid_file = _pid_file_path(args, config_path)
    state_file = _state_file_path(args, config_path)

    if args.background and not args.foreground_internal:
        running_pid = _read_pid_file(pid_file)
        if running_pid and _process_alive(running_pid):
            print(f"Daemon already running with pid {running_pid}")
            return

        cmd = [
            sys.executable,
            "-m",
            "s3sync.cli",
            "start",
            "-c",
            str(config_path),
            "--pid-file",
            str(pid_file),
            "--state-file",
            str(state_file),
            "--foreground-internal",
        ]

        with open(os.devnull, "rb") as stdin_fh, open(os.devnull, "ab") as out_fh:
            subprocess.Popen(
                cmd,
                stdin=stdin_fh,
                stdout=out_fh,
                stderr=out_fh,
                start_new_session=True,
                cwd=str(Path.cwd()),
            )

        # Wait briefly for PID file to appear.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            pid = _read_pid_file(pid_file)
            if pid and _process_alive(pid):
                print(f"Started daemon in background (pid {pid})")
                print(f"PID file:   {pid_file}")
                print(f"State file: {state_file}")
                return
            time.sleep(0.2)

        print(
            "Background start requested, but PID file did not become ready in time.",
            file=sys.stderr,
        )
        sys.exit(1)

    daemon = SyncDaemon(config_path, pid_file=pid_file, state_file=state_file)
    try:
        daemon.run()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def cmd_stop(args) -> None:
    _send_signal(args, signal.SIGTERM, "stop")


def cmd_pause(args) -> None:
    if not hasattr(signal, "SIGUSR1"):
        print("Pause is not supported on this platform", file=sys.stderr)
        sys.exit(1)
    _send_signal(args, signal.SIGUSR1, "pause")


def cmd_resume(args) -> None:
    if not hasattr(signal, "SIGUSR2"):
        print("Resume is not supported on this platform", file=sys.stderr)
        sys.exit(1)
    _send_signal(args, signal.SIGUSR2, "resume")


def cmd_reload(args) -> None:
    if not hasattr(signal, "SIGHUP"):
        print("Reload is not supported on this platform", file=sys.stderr)
        sys.exit(1)
    _send_signal(args, signal.SIGHUP, "reload")


def cmd_daemon_status(args) -> None:
    config_path = _config_path(args)
    pid_file = _pid_file_path(args, config_path)
    state_file = _state_file_path(args, config_path)

    pid = _read_pid_file(pid_file)
    running = bool(pid and _process_alive(pid))
    state = _read_json(state_file) or {}

    payload = {
        "running": running,
        "pid": pid,
        "pid_file": str(pid_file),
        "state_file": str(state_file),
        "state": state,
    }
    print(json.dumps(payload, indent=2))


def cmd_search(args) -> None:
    from .config import load_config
    from .index import SyncIndex

    cfg = load_config(_config_path(args))
    db = Path(cfg.log_file).parent / ".s3sync_index.db" if cfg.log_file else Path(".s3sync_index.db")
    index = SyncIndex(db)
    results = index.search(args.query, limit=args.limit)
    if not results:
        print("No results.")
        return
    for r in results:
        print(f"  {r.rel_path}  ({r.size:,} bytes)  [{r.status}]  s3://{cfg.s3_bucket}/{r.s3_key}")
    index.close()


def cmd_ls(args) -> None:
    from .config import load_config
    from .index import SyncIndex

    cfg = load_config(_config_path(args))
    db = Path(cfg.log_file).parent / ".s3sync_index.db" if cfg.log_file else Path(".s3sync_index.db")
    index = SyncIndex(db)
    results = index.list_folder(args.path, limit=args.limit)
    if not results:
        print("No files under that path.")
        return
    for r in results:
        print(f"  {r.rel_path}  ({r.size:,} bytes)  [{r.status}]")
    index.close()


def cmd_pull(args) -> None:
    from .config import load_config
    from .engine import SyncEngine
    from .index import SyncIndex
    from .patterns import ExclusionFilter

    cfg = load_config(_config_path(args))
    db = Path(cfg.log_file).parent / ".s3sync_index.db" if cfg.log_file else Path(".s3sync_index.db")
    index = SyncIndex(db)
    exclusion = ExclusionFilter(cfg.exclude_file)
    engine = SyncEngine(cfg, index, exclusion)
    dest = Path(args.dest).resolve()
    ok = engine.pull_file(args.rel_path, dest)
    engine.shutdown()
    index.close()
    if not ok:
        sys.exit(1)


def cmd_status(args) -> None:
    from .config import load_config
    from .index import SyncIndex

    cfg = load_config(_config_path(args))
    db = Path(cfg.log_file).parent / ".s3sync_index.db" if cfg.log_file else Path(".s3sync_index.db")
    index = SyncIndex(db)
    stats = index.stats()
    print(json.dumps(stats, indent=2))
    index.close()


def cmd_init(args) -> None:
    """Copy starter config.yaml and .syncignore into the current directory."""
    pkg_dir = Path(__file__).resolve().parent.parent
    for name in ("config.yaml", ".syncignore"):
        src = pkg_dir / name
        dest = Path(name)
        if dest.exists():
            print(f"  skip  {name} (already exists)")
        elif src.exists():
            shutil.copy2(str(src), str(dest))
            print(f"  created  {name}")
        else:
            print(f"  missing  {name} in package")


# -- argument parser -------------------------------------------------------


def _add_daemon_file_args(sp) -> None:
    sp.add_argument("-c", "--config", default="config.yaml", help="Path to config.yaml")
    sp.add_argument("--pid-file", default="", help="Path to daemon PID file")
    sp.add_argument("--state-file", default="", help="Path to daemon state JSON file")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s3sync",
        description="Cross-platform S3 file synchronisation daemon.",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    # start
    sp = sub.add_parser("start", help="Run the sync daemon")
    _add_daemon_file_args(sp)
    sp.add_argument("-b", "--background", action="store_true", help="Run daemon in background")
    sp.add_argument("--foreground-internal", action="store_true", help=argparse.SUPPRESS)

    # daemon controls
    for name, help_text in (
        ("stop", "Stop the running daemon"),
        ("pause", "Pause syncing without exiting daemon"),
        ("resume", "Resume syncing after pause"),
        ("reload", "Reload config/exclusions in running daemon"),
        ("daemon-status", "Show running daemon status"),
    ):
        sp = sub.add_parser(name, help=help_text)
        _add_daemon_file_args(sp)

    # search
    sp = sub.add_parser("search", help="Search the local file index")
    sp.add_argument("-c", "--config", default="config.yaml")
    sp.add_argument("query", help="Search term (supports prefix matching)")
    sp.add_argument("-n", "--limit", type=int, default=50)

    # ls
    sp = sub.add_parser("ls", help="List files under a path prefix")
    sp.add_argument("-c", "--config", default="config.yaml")
    sp.add_argument("path", help="Folder prefix, e.g. 'photos/2024'")
    sp.add_argument("-n", "--limit", type=int, default=200)

    # pull
    sp = sub.add_parser("pull", help="Download a single file from S3")
    sp.add_argument("-c", "--config", default="config.yaml")
    sp.add_argument("rel_path", help="Relative path as stored in the index")
    sp.add_argument("dest", help="Local destination path")

    # status
    sp = sub.add_parser("status", help="Show index stats")
    sp.add_argument("-c", "--config", default="config.yaml")

    # init
    sub.add_parser("init", help="Generate starter config.yaml and .syncignore")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "reload": cmd_reload,
        "daemon-status": cmd_daemon_status,
        "search": cmd_search,
        "ls": cmd_ls,
        "pull": cmd_pull,
        "status": cmd_status,
        "init": cmd_init,
    }
    fn = commands.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)
    try:
        fn(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
