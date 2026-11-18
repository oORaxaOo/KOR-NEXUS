# Hermes-Integration – Implementierungsstand

Stand: 2026-11-18  
Zielversion: KOR-NEXUS 1.20.0  
Zielbranch: transfer/kor-nexus-1.20.0

## Implementiert

- Optionaler MCP-Server über STDIO mit acht lesenden Werkzeugen sowie vier begrenzten Werkzeugen zum Erstellen/Bearbeiten von Aufgaben und strukturierten Einträgen.
- Loopback-only API-Client; keine direkten SQLite-, Shell- oder Dateisystemwerkzeuge.
- Native Hermes-Gateway-Plattform `kor_nexus` für Nachrichten aus dem KOR-NEXUS-HUD, inklusive eigenständigem User-Plugin-Einstiegspunkt.
- Eingebettetes Lilith-Chatfenster mit eigener Browsersitzung und Statusanzeige.
- Private lokale Bridge mit zufälligem Zugriffstoken, Loopback-Bindung, 0600-Datei und 0700-Konfigurationsverzeichnis.
- Optionale Installation; KOR-NEXUS bleibt ohne Hermes betriebsfähig.
- Client-, Bridge-, API- und Plattformtests sowie Browser-Smoke-Test.

## Noch nicht Bestandteil dieser Ausbaustufe

- Proaktive Ereignis-Pushmeldungen aus dem KOR-NEXUS Event Journal an WhatsApp, Discord oder das HUD.
- Kritische Aktionen wie Ressourcenbewegungen, Import/Restore oder Datenbanklöschungen über Lilith.
- Token-/Sitzungsverwaltung für mehrere lokale Benutzer.

Diese Funktionen bleiben als nächste Ausbaustufe vorgesehen. Die vorhandenen Sicherheits- und Bestätigungsmechanismen des KOR-NEXUS-Kerns werden nicht umgangen.

## Validierung

Der Release-Workflow muss die portable Qualitätsprüfung sowie den nativen Arch-Paket- und Installationstest erfolgreich abschließen, bevor diese Integration in den Zielbranch übernommen wird.
