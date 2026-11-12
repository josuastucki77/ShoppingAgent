# Was auf deinem PC noch benötigt wird

Prüfstand: 12. November 2026. Das Repository war zu Beginn leer.

| Komponente | Prüfung | Nächster Schritt |
| --- | --- | --- |
| Git | Vorhanden | Kein zusätzlicher Git-Client nötig |
| Python | 3.12.6 vorhanden | Diagnose- und Vorbereitungsscripts ausführbar |
| Node.js | 22.11.0 vorhanden | Für dieses Setup nicht erforderlich |
| Git Bash | Vorhanden | `bash setup.sh` möglich |
| WSL2 | `wsl --status` meldet keine Installation | WSL2 einrichten |
| Docker Desktop / Compose | Kein Docker-Befehl und keine Installation an den üblichen Benutzer-/Systempfaden gefunden | Docker Desktop installieren, Linux-Container und WSL2 verwenden |
| Ollama | `192.168.1.111:11434`, Version 0.19.0 erreichbar | Vorhandenen Server verwenden |
| Chatmodell | `llama3.1:8b`, `llama3.2:latest`, `translategemma:4b` vorhanden | Llama 3.1 als Basis; echter einfacher Werkzeugaufruf erfolgreich |
| Kontext | Beim Test 4.096 Tokens geladen | Separate Modellvariante mit 32.768 Tokens vorbereiten |
| Embeddings | Kein Embedding-Modell in der Modellliste | `nomic-embed-text` auf dem Ollama-Server laden |
| Galaxus MCP | Initialisierung und `search_products`-Werkzeugliste erfolgreich | Zugriff aus Docker beim Setup erneut prüfen |

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
Embedding-Modell und legt eine zusätzliche Variante des bestehenden Llama an.
Dieser Schritt wurde in der Vorbereitung noch nicht ausgeführt. Er benötigt
keinen Zugriff auf die Desktopoberfläche des Ollama-Rechners.

Ein kostenpflichtiger Modellzugang, ein Galaxus-Konto und ein gehostetes
Honcho-Konto sind für diese Konfiguration nicht nötig. Internetzugang bleibt
für Softwaredownloads und Galaxus erforderlich. Der Docker-Stack benötigt
LAN-Zugriff auf TCP-Port 11434 des Ollama-Servers.

## Noch offene Abnahme

- Compose-Konfiguration mit `docker compose config --quiet` und Containerstart.
- Embedding-Aufruf und Modellvariante mit größerem Kontext.
- Funktion der Kombination Honcho, lokalem Llama und dessen strukturierten Antworten.
- Neue Hermes-Session und Containerneustart mit nachweislicher Honcho-Erinnerung.
- Echte Galaxus-Recherche innerhalb von Hermes.
- Erfolgreicher manueller Lauf des täglichen Hermes-Jobs.

Die Python-Tests prüfen Datenerhalt und Idempotenz des Bootstrap-Codes,
Identitätsschutz, Job-Erkennung und MCP-Antwortverarbeitung. Sie ersetzen
die oben genannten Integrationsprüfungen nicht.

Erfolgreich geprüft: sechs Python-Tests, Python-/Bash-/PowerShell-Syntax,
Compose-YAML gegen das offizielle Compose-Schema sowie eine direkte
Galaxus-MCP-Suche mit drei echten Produkttreffern. Der lokale, von Git
ausgeschlossene Nachweis liegt in `output/mcp-proof.json`. Das PowerShell-Setup
wurde bis zur erwarteten Meldung über das fehlende Docker ausgeführt; `.env`
mit zufälligem Datenbankpasswort ist bereits angelegt und wird von Git ignoriert.
