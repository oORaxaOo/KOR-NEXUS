# Hermes-Integration für KOR-NEXUS

Diese optionale Integration verbindet Hermes Agent über einen eigenständigen MCP-Server mit der lokalen KOR-NEXUS-Instanz.

## Sicherheits- und Architekturgrenzen

- MCP verwendet stdio. Hermes startet den Server als Kindprozess; es wird kein zusätzlicher Netzwerkport geöffnet.
- Der Adapter spricht ausschließlich mit der lokalen KOR-NEXUS-HTTP-API.
- Der Adapter öffnet niemals die SQLite-Datenbank, liest keine Backups und besitzt keine Shell- oder Dateisystemwerkzeuge.
- Phase I stellt ausschließlich lesende GET-Werkzeuge bereit. POST, PATCH, DELETE und PUT werden bereits im API-Client abgewiesen.
- Inhalte aus KOR-NEXUS sind Daten und dürfen keine System- oder Toolrichtlinien überschreiben.
- Der Installer bearbeitet die Hermes-Konfiguration nicht automatisch.

## Voraussetzungen

- KOR-NEXUS muss lokal gestartet sein.
- Python 3.11 oder neuer.
- Hermes Agent mit MCP-Unterstützung.
- Internetzugriff während der einmaligen Installation des MCP-Python-SDK.

## Installation

Im KOR-NEXUS-Projektordner:

    bash integrations/hermes/install.sh

Der Installer legt eine separate virtuelle Umgebung und eine Konfigurationsvorlage unter dem KOR-NEXUS-Datenverzeichnis an (Standard: ~/.local/share/kor-workstation/hermes-integration/). Hermes selbst und die KOR-NEXUS-Core-Abhängigkeiten werden nicht verändert.

Öffne anschließend die erzeugte hermes-mcp-config.yaml und übernimm deren kor_nexus-Eintrag in den bestehenden mcp_servers-Abschnitt deiner ~/.hermes/config.yaml. Einen vorhandenen mcp_servers-Abschnitt nicht doppelt anlegen.

Die Vorlage setzt keine feste API-Adresse. Der MCP-Client liest runtime.json im KOR-NEXUS-Datenverzeichnis aus und erkennt dadurch auch einen automatisch ausgewählten Port. Optional kann KOR_NEXUS_BASE_URL im env-Abschnitt auf eine andere lokale Adresse gesetzt werden.

Anschließend:

    hermes mcp test kor_nexus

Danach eine neue Hermes-Sitzung öffnen oder /reload-mcp verwenden.

## Verfügbare Werkzeuge (read-only, Phase I)

| Werkzeug | Zweck |
|---|---|
| kor_get_status | Core-Status und Datenbankintegrität abrufen |
| kor_list_tasks | Aufgaben auflisten |
| kor_list_projects | Projekte auflisten |
| kor_list_records | Atlas-, Archiv-, Simulations- und Datenbankeinträge auflisten |
| kor_list_resources | Ressourcenbestand abrufen |
| kor_get_alerts | Engine-Warnmeldungen abrufen |
| kor_get_dashboard | Regionale Projektübersicht abrufen |
| kor_get_events | Ereignisse ab einem Journal-Cursor abrufen |

Listenwerkzeuge liefern höchstens 200 Einträge; Ereignisabfragen höchstens 500 Ereignisse.

## Fehlerbehebung

- KOR-NEXUS ist lokal nicht erreichbar: KOR-NEXUS starten und anschließend runtime.json beziehungsweise KOR_NEXUS_BASE_URL prüfen.
- Das MCP-Paket fehlt: integrations/hermes/install.sh erneut ausführen.
- Der Server erscheint nicht: den Eintrag unter mcp_servers prüfen und MCP neu laden.
- Diagnosemeldungen werden an stderr ausgegeben; stdout bleibt dem MCP-Protokoll vorbehalten.

## Tests

    PYTHONPATH=integrations/hermes/mcp_server python3 -m unittest discover -s integrations/hermes/mcp_server/tests -v
    python3 -m py_compile integrations/hermes/mcp_server/kor_client.py integrations/hermes/mcp_server/server.py
    bash -n integrations/hermes/install.sh
