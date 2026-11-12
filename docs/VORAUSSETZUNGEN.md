# Was auf deinem PC noch benötigt wird

Prüfstand: 12. November 2026. Das Repository war zu Beginn leer.

| Komponente | Prüfung | Nächster Schritt |
| --- | --- | --- |
| Git | Vorhanden | Kein zusätzlicher Git-Client nötig |
| Python | 3.12.6 vorhanden | Diagnose- und Vorbereitungsscripts ausführbar |
| Node.js | 22.11.0 vorhanden | Für dieses Setup nicht erforderlich |
| Git Bash | Vorhanden | `bash setup.sh` möglich |
| WSL2 | Inzwischen vom Nutzer installiert | Vorhandene Installation verwenden |
| Docker Desktop / Compose | Compose v5.7.0, Linux-Engine läuft | Containerstart erfolgreich geprüft |
| Ollama | `192.168.1.111:11434`, Version 0.40.16 nach Nutzer-Update erreichbar | Vorhandenen Server verwenden |
| Chatmodell | `qwen3.5:9b-q4_K_M` heruntergeladen und ausgewählt | Modell-, Schema-, MCP- und abschließender Shopping-Test bestanden |
| Kontext | Separate Variante `shopping-qwen3.5-9b:latest` mit 65.536 Tokens eingerichtet | Hermes verlangt mindestens 64.000 Tokens |
| Embeddings | `nomic-embed-text:latest` vorhanden; 768 Dimensionen erfolgreich geprüft | Bereits eingerichtet |
| Galaxus MCP | Initialisierung und `search_products`-Werkzeugliste auch aus Docker erfolgreich | Bereits verbunden |

## Installation auf Windows

1. WSL2 nach [Microsoft-Anleitung](https://learn.microsoft.com/windows/wsl/install)
   einrichten; gegebenenfalls in einer administrativen PowerShell
   `wsl --install` ausführen und Windows neu starten.
2. [Docker Desktop für Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
   installieren und starten. WSL2-Backend und Linux-Container verwenden.
3. In einer neuen PowerShell prüfen:

   ```powershell
   wsl --version
   docker version
   docker compose version
   ```

Für die WSL-/Virtualisierungsfunktionen können Windows-Administratorrechte
und ein Neustart erforderlich sein. Ob die Hardwarevirtualisierung aktiviert
ist, konnte in dieser Sitzung nicht festgestellt werden.

Docker nennt mindestens 8 GB System-RAM. Für diesen Stack sind als
Planungswert 16 GB RAM auf dem PC und etwa 20 GB freier Speicherplatz sinnvoll.
Die tatsächliche Belegung hängt von Images und Daten ab. Der Ollama-Rechner
benötigt zusätzlich Speicher für das Modell und das größere Kontextfenster.
RAM und freier Plattenspeicher wurden hier nicht zuverlässig ermittelt.
Auf dem Docker-PC ist keine zusätzliche GPU erforderlich, da Ollama im LAN läuft.

## Was du danach ausführst

```powershell
python scripts/prepare_ollama.py --apply
python scripts/check_services.py --inference
.\setup.ps1
```

`--apply` verändert den konfigurierten Ollama-Server: Es lädt das fehlende
Basis- und Embedding-Modell und legt eine zusätzliche Qwen-Variante an.
Dieser Schritt ist auf dem aktuellen Server bereits ausgeführt. Er benötigt
keinen Zugriff auf die Desktopoberfläche des Ollama-Rechners. Eine bestehende
Shopping-Modellvariante lässt sich mit zusätzlichem `--update-context`
bewusst auf die konfigurierten 65.536 Tokens aktualisieren.

Ein kostenpflichtiger Modellzugang, ein Galaxus-Konto und ein gehostetes
Honcho-Konto sind für diese Konfiguration nicht nötig. Internetzugang bleibt
für Softwaredownloads und Galaxus erforderlich. Der Docker-Stack benötigt
LAN-Zugriff auf TCP-Port 11434 des Ollama-Servers.

## Geprüfter Betrieb

Die Ollama-VM hat laut Nutzer eine RTX 3070 per PCI-Passthrough und 16 GB RAM.
Qwen3.5-9B Q4_K_M belegt bei 65.536 Kontext-Tokens gemessen 8,61 GB gesamt,
davon 6,82 GB auf der GPU. Es nutzt zusätzlich CPU/RAM. Die Einzeltests für
Deutsch, längeren Eingangstext, Werkzeugaufrufe, strukturierte Antworten und
echte Galaxus-Suche bestehen. Der abschließende Shopping-Lauf lieferte in
rund 160 Sekunden eine Empfehlung mit verifiziertem Preis und Produktlink.
Die schnellere 4B-Variante besteht Einzeltests, ist im Agenten aber weniger zuverlässig.
Der isolierte Honcho-Test mit dem dauerhaft ausgewählten 9B-Modell ist ebenfalls
bestanden: Interessen, Budget und abgelehnte Cloud-Abos wurden in einer zweiten
Sitzung korrekt abgerufen (26,70 Sekunden einschließlich Worker-Wartezeit).
Messungen und Grenzen: [MODELLTEST.md](MODELLTEST.md).

Das vollständige PowerShell-Setup wurde mehrfach erfolgreich ausgeführt.
PostgreSQL, Redis und Honcho sind gesund; der Honcho-Worker und Hermes laufen.
Der Scheduler ist aktiv, täglich um 09:00 Europe/Zurich. Die zehn Python-Tests
prüfen unter anderem Datenerhalt, Idempotenz, Identitätsschutz, Kontextgröße
und MCP-Antwortverarbeitung. Python-, Bash-, PowerShell- und Compose-Konfiguration
wurden ebenfalls geprüft. Zugangsdaten und Laufzeitnachweise sind von Git ausgeschlossen.

Das aktuelle Honcho-Plugin überspringt Cron-Agenten. Ein offizieller Hermes-
Vorbereitungsschritt liest daher das Profil vor dem Job direkt aus Honcho.
Normale Chats verwenden weiterhin das Plugin. Der isolierte Gedächtnistest
ersetzt noch keine Abnahme persönlicher Chat-Erinnerungen nach einem vollständigen
Containerneustart. Das sollte mit eigenen Vorlieben separat vorgeführt werden.

Der ursprüngliche Versuch mit Llama 3.1 8B wurde nach acht Minuten ohne Antwort
abgebrochen: rund 18 GB Gesamtbelegung bei rund 7 GB GPU-Anteil waren für diese
VM ungeeignet. Granite 4 3B-H war schnell, lieferte im vollständigen Agenten aber
fehlerhafte Werkzeugaufrufe und erfundene Produkte. Beide sind nicht mehr die
Standardmodelle dieses Projekts.
