# KOR-NEXUS: HUD, Geodaten und Flatpak

## BKG-Bundesländer importieren
Der Importer lädt die offizielle VG250-Länder-Ebene vom BKG, konvertiert die Geometrien mit GDAL/ogr2ogr nach WGS84 (EPSG:4326), prüft exakt 16 unterschiedliche Bundesländer und schreibt GeoJSON sowie SQLite. Es lädt nichts automatisch im Hintergrund.
Unter Arch Linux: \`sudo pacman -S gdal\`, danach aus dem Repository: \`python3 scripts/import-bkg-data.py\`.
Quellenvermerk bei Weitergabe/Anzeige: BKG, dl-de/by-2-0. Der Import benötigt Internet für den Download; die importierte Karte ist danach lokal verfügbar.

## HUD
\`web/js/hud-alerts.js\` enthält einen reinen SVG-Linienchart-Renderer sowie Big-Screen- und Kiosk-CSS-Zustände, Projektstatushinweise, eine Logkonsole und die Mesh-Statusanzeige. Big Screen ist zunächst aus; F11 schaltet ihn um, Escape beendet Big Screen und Kiosk-Layout. Kiosk-Layout blendet die App-interne Kopf-/Seitennavigation aus, fordert aber keinen Betriebssystem-Vollbildmodus an.

## LAN-Erkennung
Die UDP-Erkennung ist absichtlich deaktiviert, bis sie explizit durch die API aktiviert wird. Es werden ausschließlich kurze Präsenz-Beacons auf UDP 8766 gesendet; keine Namen, Dateien oder SQLite-Inhalte. Peer-Erkennung ist keine sichere Synchronisierung und überträgt keine Nutzdaten.

## Flatpak
Manifest: \`org.oORaxaOo.KorNexus.json\`. Der Build verwendet das lokale Quellverzeichnis und setzt voraus, dass die Flatpak-Runtime Python 3 bereitstellt. Die Sandbox benötigt Netzwerkfreigabe für optionale RSS-Feeds und localhost-Kommunikation. Vor einer Veröffentlichung muss der Build mit flatpak-builder auf einer realen Linux-Installation geprüft werden; dieses Manifest ist noch nicht als erfolgreich gebaute Release-Datei verifiziert.
