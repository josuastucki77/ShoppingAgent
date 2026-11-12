"""Explicitly provision only the two models this project needs on the LAN server."""

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

from check_services import json_request, load_dotenv


def stream_request(url, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.getenv("OLLAMA_API_KEY", "ollama"),
    })
    with urllib.request.urlopen(request, timeout=300) as response:
        previous = None
        for line in response:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("error"):
                raise RuntimeError(item["error"])
            status = item.get("status", "")
            percent = int(item.get("completed", 0) * 100 / item["total"]) if item.get("total") else None
            progress = (status, None if percent is None else percent // 10)
            if progress != previous:
                print(status + (f" {percent}%" if percent is not None else ""), flush=True)
                previous = progress


def main():
    parser = argparse.ArgumentParser(description="Ollama-Modelle fuer Hermes und Honcho vorbereiten")
    parser.add_argument("--apply", action="store_true",
                        help="Basis-/Embedding-Modell herunterladen und Kontext-Variante erstellen")
    parser.add_argument("--update-context", action="store_true",
                        help="Vorhandene separate Modellvariante mit dem konfigurierten Kontext neu erstellen")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    base = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.111:11434/v1").rstrip("/").removesuffix("/v1")
    original = os.getenv("OLLAMA_BASE_MODEL", "qwen3.5:9b-q4_K_M")
    target = os.getenv("OLLAMA_MODEL", "shopping-qwen3.5-9b:latest")
    embedding = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest")
    context = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "65536"))
    if context < 64000:
        raise ValueError("Diese Hermes-Version benoetigt mindestens 64000 Kontext-Tokens.")
    if target == original:
        raise ValueError("OLLAMA_MODEL muss einen anderen Namen als OLLAMA_BASE_MODEL haben.")
    print(f"Server: {base}\nEmbedding: {embedding}\nVariante: {target}, Basis {original}, Kontext {context}")
    if not args.apply:
        print("Keine Aenderung. Mit --apply werden diese Modelle auf dem Server vorbereitet.")
        return
    names = {item["name"] for item in json_request(base + "/api/tags")["models"]}
    if original not in names:
        stream_request(base + "/api/pull", {"model": original})
    if embedding not in names:
        stream_request(base + "/api/pull", {"model": embedding})
    if target not in names or args.update_context:
        stream_request(base + "/api/create", {
            "model": target, "from": original, "parameters": {"num_ctx": context, "temperature": 0.2},
        })
    else:
        info = json_request(base + "/api/show", {"model": target})
        match = re.search(r"(?m)^\s*num_ctx\s+(\d+)\s*$", info.get("parameters", ""))
        if not match or int(match.group(1)) != context:
            raise RuntimeError(f"{target} existiert bereits mit abweichendem Kontext. "
                               "Zum bewussten Aktualisieren: --apply --update-context")
        print(f"Bestehende Variante {target} bleibt erhalten.")
    print("Modelle vorbereitet. Naechster Schritt: python scripts/check_services.py --inference")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise SystemExit(f"Ollama-Vorbereitung fehlgeschlagen: {exc}")
