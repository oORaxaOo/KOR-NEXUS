# KOR-NEXUS unter NyarchLinux / Arch Linux mit KDE Plasma

KOR-NEXUS kann ohne Root-Rechte benutzerspezifisch oder als natives Arch-Paket installiert werden.

## Empfohlen: einmal einrichten, danach per Klick

### Variante A — ohne Administratorrechte

1. Das vollständige Repository oder Quellarchiv herunterladen und entpacken.
2. Im Projektordner einmal `bash install-and-launch.sh` ausführen.
3. Danach **KOR-NEXUS** über das KDE-Anwendungsmenü starten.

Der Menüeintrag wird unter `~/.local/share/applications/` registriert und das Symbol unter `~/.local/share/icons/` installiert. Das ist eine benutzerspezifische Installation.

### Optional: Desktop-Symbol

Nach der Benutzerinstallation einmal im Projektordner ausführen:

```bash
bash create-kde-desktop-shortcut.sh
```

KDE Plasma kann bei selbst erstellten Desktop-Dateien eine Sicherheitsbestätigung verlangen. Der Menüeintrag funktioniert unabhängig davon.

### Variante B — natives Arch-Paket

Als normaler Benutzer im vollständigen Projektordner ausführen:

```bash
bash install-arch-package.sh
```

Das Skript erzeugt das Quellarchiv, baut das Paket mit `makepkg` und übergibt die Installation anschließend an `sudo pacman`. Pakete dürfen nicht als root gebaut werden. Das Paket registriert Launcher und Symbol systemweit im KDE-Anwendungsmenü.

Deinstallation: `sudo pacman -R kor-workstation`. Die Benutzerdaten und Backups werden dabei nicht absichtlich gelöscht.

Voraussetzungen: Arch Linux oder eine Arch-basierte Distribution mit `base-devel`, Python 3 und funktionierender sudo-Konfiguration. `makepkg --syncdeps` kann zur Installation fehlender Build-Abhängigkeiten eine Administratorbestätigung verlangen.

## Start, Stop und Diagnose

- Start: KDE-Anwendungsmenü → **KOR-NEXUS**
- Stop: `kor-workstation-stop`
- Standardprotokoll: `~/.local/state/kor-workstation/server.log`
- Benutzerdaten: `~/.local/share/kor-workstation/`

KOR-NEXUS bindet ausschließlich an `127.0.0.1`. Chromium/Chrome wird für ein separates App-Fenster bevorzugt; andernfalls wird ein verfügbarer Browser verwendet.

## Teststatus

GitHub Actions baut das Arch-Paket in einem Arch-Linux-Container und führt einen isolierten Paketinstallations-, Start-, Stop- und Datenerhalt-Test aus. Das ersetzt keinen manuellen Test auf jeder NyarchLinux/KDE-Plasma-Version; insbesondere Desktop-Verknüpfungen hängen von der Plasma-Konfiguration ab.
