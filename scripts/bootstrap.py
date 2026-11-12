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
        from ruamel.yaml import YAML  # Parser provided by the official Hermes image.
        result = YAML(typ="safe").load(raw)
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
            "provider": "custom", "default": env.get("OLLAMA_MODEL", "shopping-qwen3.5-9b:latest"),
            "base_url": env.get("OLLAMA_BASE_URL", "http://192.168.1.111:11434/v1"),
            "api_key": "${OPENAI_API_KEY}",
            "ollama_num_ctx": int(env.get("OLLAMA_CONTEXT_LENGTH", "65536")),
        },
        "timezone": env.get("TZ", "Europe/Zurich"),
        "agent": {"max_turns": 15, "run_budget_seconds": 900, "reasoning_effort": "none"},
        "tools": {"tool_search": {"enabled": "off"}, "connectors": {"enabled": False}},
        "platform_toolsets": {
            "cli": ["terminal", "file", "memory", "cronjob"],
            "cron": ["terminal", "file", "memory"],
        },
        "auxiliary": {
            "compression": {"provider": "main", "reasoning_effort": "none"},
            "title_generation": {"provider": "main", "reasoning_effort": "none"},
            "background_review": {"enabled": False},
        },
        "terminal": {"backend": "local", "cwd": "/opt/data"},
        "memory": {"provider": "honcho", "memory_enabled": False, "user_profile_enabled": False},
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
    guide_source = project / "prompts" / "shopping-guide.md"
    if guide_source.exists():
        guide = home / "AGENTS.md"
        managed_marker = "<!-- shopping-agent-managed-context -->"
        previous = guide.read_text(encoding="utf-8") if guide.exists() else ""
        if not guide.exists() or previous.startswith(managed_marker):
            content = guide_source.read_text(encoding="utf-8").replace(
                "{{MODEL}}", env.get("OLLAMA_MODEL", "shopping-qwen3.5-9b:latest"))
            if content != previous:
                if guide.exists():
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    shutil.copy2(guide, guide.with_name(f"AGENTS.md.{stamp}.bak"))
                guide.write_text(content, encoding="utf-8")
    for directory in ["cron/output", "shopping", "scripts"]:
        (home / directory).mkdir(parents=True, exist_ok=True)
    context_script = project / "scripts" / "cron_context.py"
    if context_script.exists():
        shutil.copyfile(context_script, home / "scripts" / "shopping_context.py")


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
    prompt = (project / "prompts" / "daily-shopping.md").read_text(encoding="utf-8")
    jobs_path = home / "cron" / "jobs.json"
    if not has_daily_job(jobs_path):
        subprocess.run([
            "hermes", "cron", "create", os.getenv("SHOPPING_CRON", "0 9 * * *"), prompt,
            "--name", JOB_NAME, "--deliver", "local",
            "--timezone", os.getenv("TZ", "Europe/Zurich"), "--workdir", "/opt/data",
            "--script", "shopping_context.py",
        ], check=True)
    else:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs = data.get("jobs", []) if isinstance(data, dict) else data
        job = next(j for j in jobs if j.get("name") == JOB_NAME)
        # Migrate only our original prompt, preserving custom prompts/scripts/schedules.
        if (not job.get("script") and job.get("prompt", "").startswith(
                "Erstelle die heutige persoenliche Produktempfehlung auf Deutsch.")):
            subprocess.run(["hermes", "cron", "edit", JOB_NAME, "--prompt", prompt,
                            "--script", "shopping_context.py"], check=True)
        print("Bestehender Shopping-Job bleibt erhalten (kein Duplikat).")
    subprocess.run(["hermes", "cron", "list"], check=True)
    print("Hermes-Konfiguration, SOUL, MCP, Honcho und Tagesjob vorbereitet.")


if __name__ == "__main__":
    main()
