"""Initialize the persistent Hermes home, then use Hermes' own plugin/cron CLI."""

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

JOB_NAME = "shopping-daily"


def read_mapping(path):
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8-sig")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        import yaml  # Shipped in the official Hermes image; accept existing YAML.
        result = yaml.safe_load(raw)
    if not isinstance(result, dict):
        raise ValueError(f"{path.name} muss ein Konfigurationsobjekt enthalten.")
    return result


def update_mapping(path, updates):
    """Merge managed fields, preserve unrelated user config, back up real changes."""
    current = read_mapping(path)

    def merge(old, new):
        for key, value in new.items():
            if isinstance(value, dict):
                previous = old.setdefault(key, {})
                if not isinstance(previous, dict):
                    previous = old[key] = {}
                merge(previous, value)
            else:
                old[key] = value

    merge(current, updates)
    content = json.dumps(current, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(path, path.with_name(path.name + "." + stamp + ".bak"))
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def configure(home, project, env, stock_soul=None):
    home.mkdir(parents=True, exist_ok=True)
    user = env.get("SHOPPING_USER", "josua")
    honcho_path = home / "honcho.json"
    old = read_mapping(honcho_path)
    if old.get("peerName") and old["peerName"] != user:
        raise ValueError("SHOPPING_USER unterscheidet sich von der bestehenden Honcho-Identitaet. "
                         "Identitaetswechsel muss bewusst separat vorgenommen werden.")
    update_mapping(home / "config.yaml", {
        "model": {
            "provider": "custom", "default": env.get("OLLAMA_MODEL", "shopping-llama3.1:latest"),
            "base_url": env.get("OLLAMA_BASE_URL", "http://192.168.1.111:11434/v1"),
            "api_key": "${OPENAI_API_KEY}",
        },
        "timezone": env.get("TZ", "Europe/Zurich"),
        "agent": {"max_turns": 15, "run_budget_seconds": 900},
        "terminal": {"backend": "local", "cwd": "/opt/data"},
        "memory": {"provider": "honcho"},
        "mcp_servers": {"galaxus": {
            "url": env.get("GALAXUS_MCP_URL", "https://mcp.galaxus.ch"),
            "timeout": 60,
        }},
    })
    update_mapping(honcho_path, {
        "enabled": True, "baseUrl": "http://honcho:8000",
        "workspace": "shopping-agent", "peerName": user, "aiPeer": "milo",
        "pinUserPeer": True, "sessionStrategy": "per-session", "saveMessages": True,
        "writeFrequency": "turn", "recallMode": "hybrid",
        "dialecticReasoningLevel": "minimal", "reasoningHeuristic": False,
    })
    soul = home / "SOUL.md"
    # The official entrypoint seeds its own SOUL before our bootstrap runs.
    stock_soul = stock_soul or Path("/opt/hermes/docker/SOUL.md")
    is_stock = (soul.exists() and stock_soul.exists()
                and soul.read_bytes() == stock_soul.read_bytes())
    if not soul.exists() or is_stock:
        shutil.copyfile(project / "SOUL.md", soul)
    for directory in ["cron/output", "shopping"]:
        (home / directory).mkdir(parents=True, exist_ok=True)


def has_daily_job(path):
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        raise ValueError("Unbekanntes Hermes-Jobformat; bestehende Jobs werden nicht veraendert.")
    return any(job.get("name") == JOB_NAME for job in jobs)


def main():
    home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    project = Path("/project")
    configure(home, project, os.environ)
    # The official image keeps PM-managed plugin dependencies in the data volume.
    # --yes-deps answers the dependency installation question for zero-touch setup.
    if not (home / "plugins" / "honcho").exists():
        subprocess.run(["hermes", "plugins", "install", "honcho", "--yes-deps", "--enable"], check=True)
    subprocess.run(["hermes", "plugins", "enable", "honcho"], check=True)
    if not has_daily_job(home / "cron" / "jobs.json"):
        prompt = (project / "prompts" / "daily-shopping.md").read_text(encoding="utf-8")
        subprocess.run([
            "hermes", "cron", "create", os.getenv("SHOPPING_CRON", "0 9 * * *"), prompt,
            "--name", JOB_NAME, "--deliver", "local",
            "--timezone", os.getenv("TZ", "Europe/Zurich"), "--workdir", "/opt/data",
        ], check=True)
    else:
        print("Bestehender Shopping-Job bleibt erhalten (kein Duplikat).")
    subprocess.run(["hermes", "cron", "list"], check=True)
    print("Hermes-Konfiguration, SOUL, MCP, Honcho und Tagesjob vorbereitet.")


if __name__ == "__main__":
    main()
