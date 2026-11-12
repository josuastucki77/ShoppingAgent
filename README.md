# Milo – AI Shopping Agent

Umsetzung der Praxisaufgabe **Build Your Own AI Shopping Agent** mit dem
offiziellen Hermes-Image, dem offiziellen Galaxus-MCP und lokalem Honcho.
Hermes und Honcho verwenden den vorhandenen Ollama-Server
`192.168.1.111:11434`; ein Cloud-API-Key ist in dieser Variante nicht erforderlich.

**Stand:** Qwen3.5-9B ist auf der RTX 3070 eingerichtet und mit echten
Modell-, MCP- und Honcho-Aufrufen geprüft. Messungen und Grenzen stehen im
[Modelltest](docs/MODELLTEST.md); den Installationsstand dokumentieren die
[PC-Voraussetzungen](docs/VORAUSSETZUNGEN.md).

## Voraussetzungen

- Docker Desktop mit WSL2, laufender Docker Engine und Linux-Containern.
- Verbindung vom PC **und aus Docker** zu `192.168.1.111:11434`.
- Dort aktuelles Ollama, `qwen3.5:9b-q4_K_M`, ein Embedding-Modell und ausreichend Arbeitsspeicher
  für ein Kontextfenster von 65.536 Tokens. Hermes verlangt mindestens 64.000.
  Die größere Kontextvariante wird
  separat angelegt und verändert das ursprüngliche Modell nicht.
- Internet für Docker-Images, Honcho-Quellcode, Hermes-Plugin und Galaxus-MCP.
- Python 3.12+ für die optionalen Diagnose-/Modellvorbereitungsscripts.
  Das Container-Setup selbst benötigt kein Python auf dem Host.

PostgreSQL und Redis werden durch Compose bereitgestellt. Node.js und eine
zusätzliche lokale Ollama-Installation auf diesem PC sind nicht nötig.

## Einmalige Vorbereitung des vorhandenen Ollama-Servers

Die folgenden Befehle werden **in diesem Repository auf deinem Windows-PC**
ausgeführt. Das Python-Script spricht den Ollama-Rechner über das LAN an.

```powershell
Copy-Item .env.example .env
python scripts/prepare_ollama.py
python scripts/prepare_ollama.py --apply
python scripts/check_services.py --inference
```

Den Kopierbefehl nur ausführen, wenn `.env` noch nicht existiert. Das Setup kann
die Datei auch selbst anlegen. `--apply` lädt das fehlende Basismodell
`qwen3.5:9b-q4_K_M` (rund 6,6 GB) und `nomic-embed-text:latest`
(ungefähr 274 MB) auf den Ollama-Server und erzeugt
die Variante `shopping-qwen3.5-9b:latest` mit `num_ctx=65536` und Temperatur 0,2. Bereits vorhandene
Modelle werden erhalten. Ohne `--apply` zeigt das Script nur die geplanten Werte.
Ein größerer Kontext braucht auf dem Ollama-Rechner zusätzlich RAM/VRAM.
Bei der getesteten RTX 3070 nutzt 9B auch CPU/RAM: gemessen etwa 8,61 GB gesamt,
davon 6,82 GB auf der GPU. Der vollständige Abschlusstest dauerte rund 160 Sekunden.
Der Denkmodus bleibt ausgeschaltet. Die schnellere 4B-Variante war im Agenten
inhaltlich weniger zuverlässig; Details und frühere Fehlversuche stehen im Modelltest.

Für eine bereits angelegte Variante mit kleinerem Kontext:

```powershell
python scripts/prepare_ollama.py --apply --update-context
```

In `.env` lassen sich Server, Modelle, Nutzeridentität, Zeitzone und Zeitplan
vor dem ersten Start ändern. Embedding-Modell und Vektordimensionen müssen
zusammenpassen; für `nomic-embed-text` sind 768 Dimensionen voreingestellt.
Spätere Änderungen am Embedding-Modell erfordern eine bewusste Datenmigration.

## Automatisch starten

PowerShell:

```powershell
.\setup.ps1
```

Linux, WSL oder Git Bash:

```bash
bash setup.sh
```

Das Setup legt `.env` bei Bedarf an, ergänzt ein zufälliges Datenbankpasswort,
prüft Ollama/MCP aus einem Container, baut Honcho aus einem festgelegten
Quellcode-Commit und startet PostgreSQL, Redis, Honcho und den Hintergrundworker.
Danach schreibt es Hermes-Konfiguration, Persönlichkeit und Honcho-Anbindung,
installiert das Honcho-Plugin inklusive Abhängigkeiten und erstellt den
Hermes-Job `shopping-daily` für täglich **09:00 Europe/Zurich**.

Das aktuelle Honcho-Plugin deaktiviert sich innerhalb von Cron-Agenten.
Deshalb liest `scripts/cron_context.py` vor jedem Lauf das aktuelle Profil
direkt aus der lokalen Honcho-API. Hermes injiziert die Ausgabe über seine
offizielle `--script`-Funktion. Dieser Schritt schreibt keine Cron-Texte in das
Nutzergedächtnis. Im interaktiven Chat verwendet Hermes die Honcho-Werkzeuge.

Der veröffentlichte Hermes-Tag lautet `v0.23.1` mit führendem `v`.
Vor dem Honcho-API-Start passt das offizielle `configure_embeddings.py` die
anfangs mit 1.536 Dimensionen angelegten leeren Vektorspalten auf 768 an.
Bei bereits befüllten, inkompatiblen Vektorspalten bricht es ab.

Für den ersten Start nach `Copy-Item .env.example .env` ergänzt das Setup das
fehlende Datenbankpasswort automatisch. Es sind keine nachträglichen
Einstellungen im Hermes-Assistenten nötig.

```text
Hermes + Scheduler ──MCP──> Galaxus
       │
       ├──> Ollama im LAN <── Honcho API + Hintergrundworker
       │                          │
       └──> lokale Ausgabe        ├── PostgreSQL + pgvector
                                  └── Redis
```

## Chat und Empfehlungen

```powershell
docker compose exec -u hermes hermes hermes chat
```

Beispiel zum Kennenlernen:

> Ich interessiere mich für Smart Home und Technik. Mein Budget ist CHF 150.
> Ich nutze Home Assistant, mag reparierbare Produkte und möchte keine Geräte
> mit zwingendem Cloud-Abo. Merke dir diese Vorlieben.

Beispiel zur Produktrecherche:

> Suche drei interessante Produkte unter CHF 150 über den Galaxus-MCP.
> Vergleiche ihre Eigenschaften und Preise und erkläre, weshalb sie zu mir passen.
> Nenne direkte Links und das verwendete Werkzeug.

Ein kleines lokales Modell kann komplexe Werkzeugketten oder die
Gedächtnisextraktion unzuverlässig ausführen. Ein erfolgreicher einfacher
Tool-Test ersetzt deshalb die folgenden Integrationsprüfungen nicht.

## Demonstration und Tests

### 1. Setup und Persönlichkeit

```powershell
docker compose ps
docker compose logs --tail 60 hermes honcho honcho-deriver
```

Im Chat nach Name, Hintergrund und Aufgabe fragen. Die Persönlichkeit stammt
automatisch aus `SOUL.md`.

### 2. Echte MCP-Recherche

```powershell
python scripts/mcp_client.py --search "Smart Home" --output output/mcp-proof.json
```

Das erzeugt einen direkten MCP-Nachweis ohne Sprachmodell. Zusätzlich den
Rechercheprompt im Hermes-Chat ausführen und dort die tatsächlichen
`search_products`-Aufrufe prüfen. JSON-Nachweis und Chat demonstrieren
verschiedene Dinge: Serverfunktion und tatsächliche Agentenintegration.

### 3. Honcho über Sessions und Neustarts

Vorlieben in einem ersten Chat mitteilen und den Chat beenden. Auf abgeschlossene
Verarbeitung im `honcho-deriver`-Log warten. Einen neuen Chat starten und über
`honcho_profile`/`honcho_search` die gespeicherten Vorlieben abfragen, ohne sie
im Prompt zu wiederholen. Konkrete Inhalte aus Honcho prüfen.

```powershell
docker compose restart database redis honcho honcho-deriver hermes
docker compose ps
```

Nach dem erneuten Hochfahren einen weiteren neuen Chat starten und denselben
Gedächtnistest wiederholen. Eine bloße Behauptung des Modells genügt nicht:
Werkzeugantworten und Honcho-Worker-Logs müssen das gespeicherte Wissen belegen.

### 4. Tagesjob sofort testen

```powershell
docker compose exec -u hermes hermes hermes cron list
docker compose exec -u hermes hermes hermes cron run shopping-daily
docker compose exec -u hermes hermes hermes cron runs shopping-daily
docker compose exec -u hermes hermes hermes cron status
```

Ergebnisse liegen unter `output/<job-id>/...md`. Erfolgreich ist der Test erst,
wenn eine echte, zu den gespeicherten Vorlieben passende Empfehlung mit Preis
und Link vorliegt und der Job einen erfolgreichen Lauf meldet. MCP-Ausfälle
müssen als Fehler erkennbar sein; sie gelten nicht als erfolgreiche Recherche.
Das Vorbereitungsscript übergibt Produktlinks aus Berichten der letzten
30 Tage, um Wiederholungen zu reduzieren; die Auswahl hängt vom Modell ab.

Der PC, Docker und der Ollama-Server müssen zur Ausführungszeit eingeschaltet
sein. Für unterbrechungsfreien Betrieb eignet sich später ein dauerhaft
laufender Docker-Host. Sommer-/Winterzeit folgt `Europe/Zurich`.

### 5. Wiederholbarkeit und lokale Tests

```powershell
.\setup.ps1
python -m unittest discover -s tests -v
```

Ein zweiter Setup-Lauf erhält Daten, angepasste Persönlichkeit, fremde
Konfigurationseinträge und vorhandene Jobs. Änderungen an verwalteten
Konfigurationsfeldern erhalten eine `.bak`-Kopie im Hermes-Volume. Der
Hermes-Dienst wird zur Konfiguration kurz gestoppt; laufende Chats vorher beenden.
Ein Identitätswechsel wird abgebrochen, damit vorhandenes Honcho-Wissen nicht
versehentlich einem anderen Nutzer zugeordnet wird.

Bei einem ursprünglichen, noch unveränderten Shopping-Prompt ergänzt das Setup
einmalig den Honcho-Vorbereitungsschritt. Eigene Prompts, Scripts und Zeitpläne
bleiben erhalten. Um den Zeitplan später
anzupassen, Hermes verwenden:

```powershell
docker compose exec -u hermes hermes hermes cron edit shopping-daily --schedule "0 9 * * *" --timezone Europe/Zurich
```

## Daten und Betrieb

Die benannten Docker-Volumes enthalten Hermes-Konfiguration und Plugin-Runtime,
Honcho-Datenbank und Redis-Daten. `output/` enthält die Empfehlungen auf dem Host.
`docker compose down` stoppt den Stack und erhält die Volumes. **`down -v`
löscht die gespeicherten Daten** und gehört nicht zum normalen Neustart.

Es werden keine Serverports des Stacks auf dem Host veröffentlicht. Honcho
verwendet innerhalb des lokalen Compose-Netzes keine API-Authentifizierung.
Für Freigaben außerhalb dieses Netzes wäre eine separate Absicherung nötig.
Die Ollama-Verbindung bleibt im LAN; Produktsuchbegriffe gehen an Galaxus.

Passwörter und eventuell später benötigte echte Tokens ausschließlich in `.env`
ablegen. `.env`, Ausgaben und Laufzeitdaten sind von Git ausgeschlossen. Das
Setup ändert keine globalen Git-Einstellungen und kopiert keine bestehenden
Anmeldedaten vom PC.

## Quellen und Abweichungen vom PDF

- [Hermes Docker](https://hermes-agent.nousresearch.com/docs/user-guide/docker)
- [Hermes Honcho-Integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/honcho)
- [Hermes Scheduler](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
- [Galaxus MCP-Ankündigung](https://www.galaxus.ch/en/page/galaxus-introduces-mcp-interface-for-ai-assistants-44216)
- [Honcho Quellcode und Compose-Beispiel](https://github.com/plastic-labs/honcho)
- [Ollama API-Kompatibilität](https://docs.ollama.com/api/openai-compatibility)

Auf Wunsch des Nutzers wird Ollama anstelle eines Abonnements oder OpenRouter
verwendet. Honcho bleibt lokal und nutzt ebenfalls Ollama für Text und Embeddings.
Aktuelles Hermes benötigt das Honcho-Plugin aus seinem Katalog; das Setup
installiert es automatisch über die offizielle CLI. Der direkte Galaxus-Endpunkt
ist `https://mcp.galaxus.ch` ohne `/mcp`. Seine Werkzeugliste wurde geprüft.
Ein alternativer MCP-Server ist derzeit nicht nötig.
