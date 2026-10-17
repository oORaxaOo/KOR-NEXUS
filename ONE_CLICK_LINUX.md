# KOR-NEXUS unter Linux: Ein-Klick-Start

KOR-NEXUS benötigt zur Laufzeit Python 3 und SQLite aus der Python-Standardbibliothek. Chromium/Chrome wird für ein eigenes App-Fenster bevorzugt; Firefox oder der Standardbrowser funktionieren ebenfalls. Es sind keine npm-Downloads, kein Cloud-Konto und keine Root-Rechte nötig.

## Einmal einrichten und sofort starten

1. Lade das vollständige Quellarchiv von GitHub herunter und entpacke es in einen normalen Benutzerordner.
2. Öffne den entpackten Ordner im Dateimanager.
3. Starte `install-and-launch.sh`. Wenn dein Dateimanager Shell-Skripte nicht direkt ausführt, öffne ein Terminal in diesem Ordner und führe `bash install-and-launch.sh` aus.
4. Das Skript installiert KOR-NEXUS nur für deinen Benutzer und startet es direkt. Die Oberfläche sollte sich in einem Browser/App-Fenster öffnen.

Manche Linux-Dateimanager behandeln Skripte aus Sicherheitsgründen nicht wie Windows-EXE-Dateien. Deshalb kann der allererste Start je nach Desktop-Umgebung eine Bestätigung oder den Terminal-Schritt erfordern. Das ist eine Einschränkung der Linux-Desktop-Umgebung, nicht der Anwendung.

## Jeder weitere Start: ein Klick

Nach der Einrichtung findest du **KOR-NEXUS** im Anwendungsmenü deiner Desktop-Umgebung. Klicke den Eintrag wie bei einem normalen installierten Programm. Der Server startet im Hintergrund und öffnet die lokale Oberfläche. Wiederholte Klicks öffnen die vorhandene Instanz erneut, statt eine zweite Datenbankinstanz zu starten.

## Beenden

- Wenn KOR-NEXUS als Browser-App-Fenster geöffnet ist, kannst du das Fenster schließen; der lokale Server bleibt für einen erneuten Klick aktiv.
- Zum gezielten Beenden kannst du `~/.local/bin/kor-workstation-stop` ausführen.
- Die Deinstallation entfernt Programmdateien und Menüeintrag, bewahrt aber die Datenbank und Backups.

## Fehlerdiagnose

Das Startprotokoll liegt standardmäßig unter `~/.local/state/kor-workstation/server.log` (oder unter `$XDG_STATE_HOME/kor-workstation/server.log`, falls gesetzt). Bei fehlendem Browser kann KOR-NEXUS weiterhin laufen; installiere dann Chromium, Firefox oder ein Paket mit `xdg-open` und starte erneut.

KOR-NEXUS bindet ausschließlich an `127.0.0.1`. Bitte nicht als öffentlich erreichbaren Netzwerkdienst veröffentlichen.
