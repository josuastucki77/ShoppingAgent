# Modelltest auf der Ollama-VM

Prüfstand: 12. November 2026. Hardware laut Nutzer: RTX 3070 per PCI-Passthrough,
16 GB VM-RAM. Ollama wurde vom Nutzer auf Version 0.40.16 aktualisiert; die
Version wurde über die API bestätigt. Version 0.19 hatte Qwen3.5 mit HTTP 412 abgelehnt.

Für Hermes werden separate Modellvarianten mit 65.536 Kontexttokens angelegt.
Downloadgröße und Laufzeitspeicher sind unterschiedliche Größen. Die Messwerte
sind einzelne lokale Durchläufe, keine repräsentative Leistungsstudie.

## Auswahl

Als Standard ist **Qwen3.5-9B Q4_K_M** eingerichtet, Alias
`shopping-qwen3.5-9b:latest`, mit ausgeschaltetem Denkmodus. Es ist auf dieser
Hardware langsamer als 4B, hat den abschließenden Shopping-Test aber mit
belegter Produktauswahl, Preis, vollständigem Link und passender Begründung bestanden.
Es nutzt bei 65.536 Kontexttokens zusätzlich CPU/RAM. Für den täglichen Job
ist die gemessene Laufzeit von rund 160 Sekunden vertretbar; für schnelle Chats
ist die 4B-Variante deutlich flotter, aber im getesteten Agenten weniger zuverlässig.

## Qwen3.5-4B Q4_K_M

Basis: `qwen3.5:4b-q4_K_M`; Variante: `shopping-qwen3.5:latest`, Temperatur 0,2.

| Prüfung | Messung / Ergebnis |
| --- | --- |
| Download | rund 3,3 GB |
| Speicher mit 65.536 Kontexttokens | 5.221.918.964 Bytes, vollständig GPU |
| Kurze deutsche Antwort, erster Aufruf mit Laden | 7,359 s; 54,85 Ausgabetokens/s |
| Kurze deutsche Antwort, bereits geladen | 1,141 s; 74,15 Ausgabetokens/s bei 58 Ausgabetokens |
| 11.938 Eingabetokens, Testkennung vom Textanfang wiederfinden | bestanden; zunächst 10,735 s |
| Wiederholung dieses langen Textes | 0,312 s, mit bereits gefülltem Promptcache |
| Einfacher Werkzeugaufruf | 3 von 3 bestanden |
| Strukturierte JSON-Vorlieben | bestanden |
| Galaxus-Schema plus echter MCP-Aufruf | bestanden mit dem Produktionsleitfaden; 1,828 s Modellzeit |
| Honcho-Extraktion und Abruf in neuer Sitzung | bestanden, 26,81 s einschließlich Worker-Wartezeit |

Die drei einfachen Werkzeugtests verwenden denselben Ping-Aufruf. Die
Langtextprüfung füllt nicht das gesamte Kontextfenster. Die Speicherangaben
stammen aus `/api/ps`; sie messen nicht die gesamte VM-RAM-Auslastung.

Ohne Leitfaden setzte auch Qwen zunächst das vom MCP abgelehnte `minPrice=0`.
Der Test validiert daher echte Serverantworten und dokumentiert den verwendeten
Leitfaden. Ein bloß ausgegebenes Tool-Call-JSON gilt nicht als erfolgreicher MCP-Test.

**Vollständiger Agent: technisch funktionsfähig, inhaltlich nicht vollständig
bestanden.** Mehrere Cron-Läufe erzeugten echte Empfehlungen in rund 17–30 s.
Produktnamen und Preise ließen sich in den MCP-Antworten wiederfinden. Es gab
aber unbelegte Vergleiche, Verwechslungen früherer Empfehlungen mit Käufen,
wiederholte Produkte und erfundene persönliche Interessen. Niedriger Denkaufwand
verbesserte die Ausgabe, beseitigte die Fehler nicht vollständig. Erfolgreicher
Cron-Exit und sieben bestandene Einzeltests belegen deshalb keine verlässliche
autonome Empfehlungsqualität.

## Qwen3.5-9B Q4_K_M

Zusätzlich heruntergeladen und mit denselben sieben Einzeltests geprüft:
`qwen3.5:9b-q4_K_M`, Variante `shopping-qwen3.5-9b:latest`.

| Prüfung | Messung / Ergebnis |
| --- | --- |
| Download | rund 6,6 GB |
| Speicher mit 65.536 Kontexttokens | 8.611.147.281 Bytes gesamt; 6.819.760.045 Bytes GPU |
| Kurze deutsche Antwort, erster Aufruf mit Laden | 15,625 s; 11,81 Ausgabetokens/s |
| Langtextprüfung, 11.938 Eingabetokens | bestanden; 21,609 s |
| Einfacher Werkzeugaufruf | 3 von 3 bestanden; 2,4–3,0 s |
| Strukturierte JSON-Vorlieben | bestanden; 4,984 s |
| Galaxus-Schema plus echter MCP-Aufruf | bestanden; 11,110 s Modellzeit |
| Honcho nach dauerhafter Umstellung auf 9B | bestanden; 26,70 s, Vorlieben in zweiter Sitzung korrekt abgerufen |

9B nutzt bei diesem Kontext auch CPU/RAM und ist deutlich langsamer als 4B.
Die Rohmessung liegt unter `.runtime/benchmarks/qwen35-9b.json`.
Ein vollständiger Lauf mit `reasoning_effort=low` wurde nach 282,04 s ohne
fertige Empfehlung kontrolliert abgebrochen. Der Zeitplan blieb erhalten.

Ein erster vollständiger Lauf ohne Denkmodus endete nach 89,64 s: Er vermied
eine frühere Empfehlung korrekt, ließ aber den geforderten Produktlink weg.
Danach wurde eine feste Ausgabevorlage ergänzt. Der abschließende Lauf dauerte
159,82 s und wählte eine Lighty-Sensorlampe für CHF 24.90. Name, Preis,
vollständiger `pageUrl`, Budget und das Fehlen früherer Berichte zu diesem
Produkt wurden anhand der tatsächlichen MCP-Antwort und Berichtshistorie geprüft.
Die beschriebene Bauweise und bedarfsgerechte Beleuchtung stehen in der Quelle;
Interesse an Smart Home und Budget stammen aus dem Honcho-Kontext.
Anschließend wurde das vollständige Setup mit 9B für Hermes und alle Honcho-
Textmodelle erfolgreich ausgeführt. Der zusätzliche isolierte Honcho-Test
bestätigte Interessen, CHF 149 Budget und Ablehnung verpflichtender Cloud-Abos;
die Testdaten wurden zur Löschung vorgemerkt. Alle fünf Dienste laufen,
die drei vorhandenen Healthchecks sind grün. Der Tagesjob bleibt bei 09:00
Europe/Zurich, mit `reasoning_effort=none` und der festen Ausgabevorlage.

Der Agent recherchierte nach den bereits bekannten Hubs erneut nach Sensoren.
Dabei forderte er trotz `first=3` im Prompt zehn Treffer an und korrigierte einen
unvollständigen Datei-Aufruf selbst. Der bestandene Abschlusslauf belegt daher
keine Fehlerfreiheit über beliebige weitere Läufe.

Lokale Nachweise:

- Bericht: `output/817a81e79243/2026-11-12_20-24-48.md`
- Produktquelle und Prüfresultate: `output/model-validation-qwen35-9b.json`
- Isolierter Gedächtnistest: `output/model-memory-test-qwen35-9b.json`

## Honcho und Cron

Das installierte Honcho-Plugin setzt in Cron ausdrücklich `_cron_skipped=True`.
Das war eine Integrationsursache für scheinbar fehlendes Gedächtnis. Der Tagesjob
nutzt jetzt Hermes' offizielle `--script`-Funktion: `scripts/cron_context.py` liest
das Profil vor jedem Lauf direkt aus der lokalen API und liefert bisherige
Produktlinks mit. Er schreibt die Job-Texte nicht in das Nutzergedächtnis.
API-Ausfälle werden nicht als leeres Profil behandelt. Im Chat bleibt das Plugin aktiv.

Der Gedächtnistest verwendet einen isolierten Testbereich mit fiktiven Interessen,
CHF 149 Budget und Ablehnung verpflichtender Cloud-Abos. Die Worker-Extraktion
enthielt alle drei Angaben; eine zweite Sitzung konnte sie ohne erneute Eingabe
abrufen. Beide Sitzungen und der Testbereich wurden anschließend zur Löschung
vorgemerkt. Das persönliche Shopping-Profil wurde damit nicht verändert.
Ein kompletter Neustart mit persönlichem Hermes-Chat ist separat zu demonstrieren.

## Verworfene Kandidaten

| Modell | Messung / Grund |
| --- | --- |
| Llama 3.1 8B | Mit 65.536 Kontexttokens rund 17,93 GB gesamt, nur 7,15 GB GPU; nach acht Minuten ohne Antwort abgebrochen |
| Granite 4 3B-H | 5,83 GB vollständig GPU; etwa 122 Ausgabetokens/s; Einzeltests und Honcho bestanden, im Agenten wiederholt ungültige Werkzeugaufrufe und erfundene Produkte |

## Nachvollziehen

```powershell
python scripts/benchmark_model.py --model shopping-qwen3.5-9b:latest --with-galaxus --output .runtime/benchmarks/qwen35-9b.json
docker compose exec -T -u hermes hermes /opt/hermes/.venv/bin/python /project/scripts/verify_memory.py
docker compose exec -T -u hermes hermes hermes cron run shopping-daily
python -m unittest discover -s tests -v
```

Die Rohmessungen liegen lokal und von Git ausgeschlossen unter
`.runtime/benchmarks/qwen35-initial.json`, `qwen35.json` und `granite4.json`.
Hermes-Werkzeugantworten liegen im persistenten Sitzungsprotokoll, Berichte unter
`output/817a81e79243/`. Dort sind auch fehlgeschlagene Qualitätsversuche enthalten.
Der isolierte Qwen-Honcho-Nachweis liegt im Hermes-Volume unter
`/opt/data/shopping/model-memory-test-qwen35.json`. Die zehn lokalen Tests prüfen
unter anderem Datenerhalt, Kontextgröße und die Honcho-Cron-Übergabe.

## Quellen

- [Qwen3.5-4B Q4_K_M bei Ollama](https://ollama.com/library/qwen3.5:4b-q4_K_M)
- [Qwen3.5-9B Q4_K_M bei Ollama](https://ollama.com/library/qwen3.5:9b-q4_K_M)
- [Qwen-Modellkarte](https://huggingface.co/Qwen/Qwen3.5-4B)
- [Ollama-Kontextgröße](https://docs.ollama.com/context-length)
- [Hermes Tool Search](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search)
- [Granite 4 3B-H bei Ollama](https://ollama.com/library/granite4:3b-h)
