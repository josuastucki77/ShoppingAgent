"""Read-only checks; never downloads models or changes the Ollama server."""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from mcp_client import MCPClient


def load_dotenv(path):
    """Read our simple dotenv template without executing shell expressions."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def json_request(url, body=None, timeout=15):
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.getenv("OLLAMA_API_KEY", "ollama")})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def check_ollama(inference=False):
    base = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.111:11434/v1").rstrip("/")
    native = base.removesuffix("/v1")
    model = os.getenv("OLLAMA_MODEL", "shopping-llama3.1:latest")
    embedding = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest")
    names = {m["name"] for m in json_request(native + "/api/tags")["models"]}
    missing = []
    for name in [model, embedding]:
        if name not in names and name + ":latest" not in names:
            missing.append(name)
    if missing:
        raise RuntimeError("Auf dem Ollama-Server fehlen: " + ", ".join(missing)
                           + ". Modelle vorbereiten: python scripts/prepare_ollama.py --apply")
    capabilities = json_request(native + "/api/show", {"model": model}).get("capabilities", [])
    if "tools" not in capabilities:
        raise RuntimeError(f"{model} meldet keine Tool-Calling-Unterstuetzung.")
    print(f"Ollama erreichbar: {model} (Werkzeugaufrufe) und {embedding} vorhanden.")
    if inference:
        response = json_request(base + "/chat/completions", {
            "model": model, "stream": False, "temperature": 0,
            "messages": [{"role": "user", "content": "Call the ping tool with value OK."}],
            "tools": [{"type": "function", "function": {
                "name": "ping", "description": "Connectivity test",
                "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                               "required": ["value"]},
            }}], "max_tokens": 100,
        }, timeout=180)
        calls = response["choices"][0]["message"].get("tool_calls", [])
        if not any(call.get("function", {}).get("name") == "ping" for call in calls):
            raise RuntimeError("Das Modell hat im Praxistest kein Werkzeug aufgerufen.")
        response = json_request(base + "/embeddings", {
            "model": embedding, "input": ["Ich interessiere mich fuer Smart Home."],
        }, timeout=120)
        actual = len(response["data"][0]["embedding"])
        expected = int(os.getenv("OLLAMA_EMBEDDING_DIMENSIONS", "768"))
        if actual != expected:
            raise RuntimeError(f"Embedding hat {actual} Dimensionen; konfiguriert sind {expected}.")
        print(f"Werkzeugaufruf und Embedding ({actual} Dimensionen) erfolgreich getestet.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", action="store_true", help="Auch echte Modellaufrufe testen")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    failed = False
    for label, check in [
        ("Ollama", lambda: check_ollama(args.inference)),
        ("Galaxus MCP", check_mcp),
    ]:
        try:
            check()
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            print(f"FEHLER {label}: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def check_mcp():
    client = MCPClient(os.getenv("GALAXUS_MCP_URL", "https://mcp.galaxus.ch"))
    client.initialize()
    tools = client.request("tools/list")["tools"]
    if not any(tool["name"] == "search_products" for tool in tools):
        raise RuntimeError("Galaxus liefert kein search_products-Werkzeug.")
    print("Galaxus MCP erreichbar; search_products vorhanden.")


if __name__ == "__main__":
    sys.exit(main())
