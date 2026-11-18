# KOR-NEXUS x Hermes — vollständige lokale Integration

KOR-NEXUS erhält zwei getrennte Integrationswege:

1. **MCP-Werkzeuge** geben Hermes lesenden Zugriff auf Status, Aufgaben, Projekte, Atlas-/Archivdatensätze, Ressourcen, Systemmetriken und den vorhandenen Nachrichten-Cache.
2. **Hermes-Plattformplugin** ergänzt KOR-NEXUS als eigenen lokalen Chat-Kanal im Hermes Gateway. Nachrichten aus der KOR-NEXUS-Oberfläche laufen durch den regulären Hermes-Agenten; Antworten erscheinen wieder im selben KOR-NEXUS-Gespräch.

KOR-NEXUS bleibt ohne Hermes vollständig funktionsfähig. Das Plugin verändert keine bestehenden Telegram-, WhatsApp-, Discord- oder anderen Hermes-Kanäle. Jede Plattform behält ihre normale Hermes-Sitzungsidentität; es findet keine automatische Zusammenführung der Chatverläufe verschiedener Plattformen statt.

## Architektur

- \`mcp_server.py\` stellt die MCP-Werkzeuge über STDIO bereit. Hermes startet den Prozess lokal; es wird kein zusätzlicher Netzwerk-Port geöffnet.
- \`kor_client.py\` spricht ausschließlich die bestehende KOR-NEXUS-HTTP-API an. Direkter SQLite-Zugriff ist ausgeschlossen.
- \`plugin/adapter.py\` registriert über die unterstützte Hermes-Community-Plugin-Schnittstelle den Plattformkanal \`kor_nexus\`.
- KOR-NEXUS speichert Nachrichten lokal in zwei zusätzlichen SQLite-Tabellen. Das Gateway fragt die eingehende Warteschlange über einen privaten Bridge-Endpunkt ab und schreibt Antworten zurück.
- Die lokale Chat-Oberfläche liegt unter \`web/hermes.html\`; in der KOR-NEXUS-Kopfzeile gibt es den Einstieg **⌘ HERMES**.

## Sicherheitsgrenzen

- KOR-NEXUS bleibt ausschließlich an \`127.0.0.1\` gebunden.
- Bridge-Endpunkte akzeptieren nur einen privaten Bearer-Token. Der Token wird mit einem konstantzeitlichen Vergleich geprüft und in einer Datei mit Berechtigungen \`0600\` gespeichert.
- Der Hermes-Adapter akzeptiert nur Loopback-HTTP-Adressen und verweigert HTTP-Weiterleitungen, damit der Bridge-Token nicht an ein anderes Ziel weitergereicht wird.
- MCP und Plattformplugin öffnen keinen LAN-Listener und greifen nicht direkt auf SQLite zu.
- Nachrichten und API-Antworten sind größenbegrenzt; die MCP-Werkzeuge bleiben ausschließlich lesend.
- Die Einrichtung ergänzt nur die KOR-NEXUS-Plugin-Dateien und die ausdrücklich benannten Variablen in \`~/.hermes/.env\`. Sie überschreibt nicht die übrige Hermes-Konfiguration.

## MCP-Werkzeuge

| Werkzeug | Zweck |
|---|---|
| \`kor_get_status\` | Programmversion, Datenbankstatus und Backup-Anzahl |
| \`kor_get_system_health\` | lokale Systemmetriken |
| \`kor_list_tasks\` | Aufgaben |
| \`kor_list_projects\` | Projektübersicht mit Region-, Status- oder ID-Filter |
| \`kor_list_records\` | Atlas-, Projekt-, Archiv-, Simulations- und Datenbankeinträge |
| \`kor_list_resources\` | Ressourcenbestand |
| \`kor_list_news\` | lokal zwischengespeicherte RSS-Meldungen, ohne Feed-Refresh |

## Installation

Voraussetzungen: KOR-NEXUS auf demselben Benutzerkonto, Hermes Agent mit Gateway und Python 3.11 oder neuer.

Aus dem Repository- oder installierten KOR-NEXUS-App-Ordner ausführen:

    bash integrations/hermes/setup.sh

Das Skript:

- richtet eine eigene Python-Umgebung für den MCP-Server ein;
- erzeugt oder erhält den privaten Bridge-Token;
- trägt die Bridge-Variablen geschützt in \`~/.hermes/.env\` ein;
- installiert das optionale Hermes-Plattformplugin unter \`~/.hermes/plugins/kor-nexus\`;
- gibt die benötigten YAML-Blöcke für \`gateway.platforms.kor_nexus\` und \`mcp_servers.kor_nexus\` aus.

Die Skript-Ausgabe enthält die absoluten Pfade für dein System. Ergänze beide YAML-Blöcke in \`~/.hermes/config.yaml\`; das Skript verändert diese Datei absichtlich nicht automatisch. Starte zuerst KOR-NEXUS und danach das Hermes Gateway neu:

    hermes gateway restart

Anschließend ist **⌘ HERMES** in KOR-NEXUS der lokale Gesprächseinstieg.

## Diagnose

Die Ausgabe von \`setup.sh\` enthält den Aufruf für:

    <MCP-VENV>/bin/python <KOR-NEXUS-APP>/integrations/hermes/doctor.py

Die Diagnose meldet Verbindung und freigegebene Statusdaten, nicht den lokalen Datenbankpfad.

## Tests

Die clientseitigen Sicherheits- und API-Tests benötigen kein MCP-Paket:

    python3 -m unittest -v tests.test_hermes_mcp_client

Die MCP-Protokolltests benötigen die optionale Abhängigkeit:

    python3 -m pip install -r integrations/hermes/requirements.txt
    PYTHONPATH=. python3 -m unittest discover -s integrations/hermes/tests -v

Die HTTP-Warteschlange und Tokenprüfung werden zusätzlich durch \`core.test_server\` getestet. Der isolierte Hermes-CI-Workflow prüft MCP-Registrierung, Python-Syntax und Setup-Skript; die allgemeine Release-Pipeline führt die Kern-API-Tests sowie die Installations- und Paketprüfungen aus.

## Bewusste Grenzen der ersten Ausbaustufe

- Hermes kann KOR-NEXUS-Daten zunächst nur lesen. Schreibende Aktionen in Aufgaben, Projekten oder Archiv benötigen später jeweils eigene validierte API-Funktionen und klare Bestätigungsschritte.
- KOR-NEXUS ist ein zusätzlicher Hermes-Kanal. Es spiegelt nicht automatisch jede eingehende Telegram-/WhatsApp-/Discord-Nachricht in die lokale KOR-NEXUS-Oberfläche.
- Die Chat-Warteschlange ist lokal und nicht für mehrere Rechner oder Benutzer ausgelegt.
