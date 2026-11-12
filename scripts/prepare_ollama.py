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
            if status != previous:
                print(status, flush=True)
                previous = status


def main():
    parser = argparse.ArgumentParser(description="Ollama-Modelle fuer Hermes und Honcho vorbereiten")
    parser.add_argument("--apply", action="store_true",
                        help="Embedding-Modell herunterladen und Kontext-Variante erstellen")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    base = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.111:11434/v1").rstrip("/").removesuffix("/v1")
    original = os.getenv("OLLAMA_BASE_MODEL", "llama3.1:8b")
    target = os.getenv("OLLAMA_MODEL", "shopping-llama3.1:latest")
    embedding = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest")
    context = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "32768"))
    if target == original:
        raise ValueError("OLLAMA_MODEL muss einen anderen Namen als OLLAMA_BASE_MODEL haben.")
    print(f"Server: {base}\nEmbedding: {embedding}\nVariante: {target}, Basis {original}, Kontext {context}")
    if not args.apply:
        print("Keine Aenderung. Mit --apply werden diese Modelle auf dem Server vorbereitet.")
        return
    names = {item["name"] for item in json_request(base + "/api/tags")["models"]}
    if original not in names:
        raise RuntimeError(f"Basismodell {original} fehlt. Bitte zuerst auf dem Server bereitstellen.")
    if embedding not in names:
        stream_request(base + "/api/pull", {"model": embedding})
    if target not in names:
        stream_request(base + "/api/create", {
            "model": target, "from": original, "parameters": {"num_ctx": context},
        })
    else:
        info = json_request(base + "/api/show", {"model": target})
        match = re.search(r"(?m)^\s*num_ctx\s+(\d+)\s*$", info.get("parameters", ""))
        if not match or int(match.group(1)) != context:
            raise RuntimeError(f"{target} existiert bereits mit abweichendem Kontext. Bitte separat pruefen.")
        print(f"Bestehende Variante {target} bleibt erhalten.")
    print("Modelle vorbereitet. Naechster Schritt: python scripts/check_services.py --inference")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise SystemExit(f"Ollama-Vorbereitung fehlgeschlagen: {exc}")
