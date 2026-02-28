import os
import signal
import subprocess
import sys
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path)
        return
    except Exception:
        pass

    # Minimal fallback loader (no variable expansion)
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _popen(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    kwargs: dict = {
        "cwd": str(cwd),
        "env": env,
    }

    # Make Ctrl+C delivery more reliable on Windows by using a new process group.
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    return subprocess.Popen(cmd, **kwargs)


def main() -> int:
    repo_root = Path(__file__).resolve().parent

    _load_env_file(repo_root / ".env")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        import openai  # noqa: F401
    except Exception:
        print("Missing dependency: openai")
        print("Install dependencies, e.g.:")
        print("  python -m pip install -r requirements/base.requirements.txt")
        return 1

    api_host = env.get("API_SERVER_HOST", "0.0.0.0")
    api_port = env.get("API_SERVER_PORT", "8000")

    api_cmd = [
        sys.executable,
        "-m",
        "calico.workflow.cli",
        "serve-api",
        "--host",
        api_host,
        "--port",
        str(api_port),
    ]

    cli_cmd = [
        sys.executable,
        "-m",
        "calico.cli.main",
    ]

    api_proc = _popen(api_cmd, cwd=repo_root, env=env)
    cli_proc = _popen(cli_cmd, cwd=repo_root, env=env)

    try:
        while True:
            api_rc = api_proc.poll()
            cli_rc = cli_proc.poll()

            if api_rc is not None:
                return api_rc
            if cli_rc is not None:
                return cli_rc

            try:
                api_proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass

    except KeyboardInterrupt:
        pass
    finally:
        for proc in (cli_proc, api_proc):
            if proc.poll() is not None:
                continue
            try:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.send_signal(signal.SIGINT)
            except Exception:
                pass

        # Give processes a moment to exit gracefully
        for proc in (cli_proc, api_proc):
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

        for proc in (cli_proc, api_proc):
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    return 130


if __name__ == "__main__":
    raise SystemExit(main())
