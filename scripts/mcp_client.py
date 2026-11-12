"""Small diagnostic client for Streamable HTTP MCP (JSON and SSE responses)."""

import json
import urllib.error
import urllib.request


class MCPClient:
    def __init__(self, url, timeout=30):
        self.url = url
        self.timeout = timeout
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.counter = 0

    @staticmethod
    def decode(raw, request_id):
        raw = raw.strip()
        if raw.startswith("{"):
            messages = [json.loads(raw)]
        else:
            messages = []
            for event in raw.replace("\r\n", "\n").split("\n\n"):
                data = "\n".join(line[5:].lstrip() for line in event.splitlines()
                                 if line.startswith("data:"))
                if data:
                    messages.append(json.loads(data))
        for message in messages:
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"MCP-Fehler: {message['error']}")
                return message.get("result", {})
        raise RuntimeError("MCP lieferte keine passende JSON-RPC-Antwort.")

    def request(self, method, params=None, notification=False):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notification:
            self.counter += 1
            body["id"] = self.counter
        request = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), headers=self.headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                self.headers["Mcp-Session-Id"] = session
            raw = response.read().decode()
        return None if notification else self.decode(raw, body["id"])

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "shopping-agent-preflight", "version": "1.0"},
        })
        self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
        self.request("notifications/initialized", notification=True)
        return result


def main():
    import argparse
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Galaxus-MCP ohne LLM testen")
    parser.add_argument("--search", help="Optional eine echte Produktsuche ausfuehren")
    parser.add_argument("--output", type=Path, help="MCP-Antwort als Nachweis speichern")
    args = parser.parse_args()
    client = MCPClient(os.environ.get("GALAXUS_MCP_URL", "https://mcp.galaxus.ch"))
    server = client.initialize()
    tools = client.request("tools/list")
    result = {"server": server["serverInfo"], "tools": tools["tools"]}
    if args.search:
        result["search"] = client.request("tools/call", {
            "name": "search_products", "arguments": {
                "query": args.search, "maxPrice": 149, "first": 3,
                "language": "de", "agentInfo": "ShoppingAgent diagnostic client, no LLM",
            },
        })
        if result["search"].get("isError"):
            raise RuntimeError("Galaxus meldet einen Fehler bei der Produktsuche.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MCP erreichbar. Werkzeuge: " + ", ".join(t["name"] for t in tools["tools"]))
    if args.search:
        print("Echte Produktsuche ausgefuehrt." + (f" Nachweis: {args.output}" if args.output else ""))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise SystemExit(f"MCP-Pruefung fehlgeschlagen: {exc}")
