# Maintainer: KOR-NEXUS project
pkgname=kor-workstation
pkgver=1.20.0
pkgrel=1
pkgdesc='Lokale SQLite-Workstation für Kor-Wissen, Projekte, Atlas und RSS'
arch=('any')
license=('custom:KOR-Project')
depends=('python' 'python-pyqt6' 'python-pyqt6-webengine')
optdepends=('chromium: separates App-Fenster im Ein-Klick-Start'
            'xdg-utils: Browser-Fallback, falls Chromium fehlt'
            'firefox: alternativer Browser')
source=("${pkgname}-${pkgver}.tar.gz")
sha256sums=('1489c6e83eba03e6856f04b39ce3ce1a20deca5e7b901f3b6ac0d30a19eb4ebb')

build() {
  cd "$srcdir"
  python -m py_compile core/server.py core/window.py
}

check() {
  cd "$srcdir"
  KOR_NO_BROWSER=1 python -m unittest -v core.test_server
  bash scripts/verify-source.sh
}

package() {
  cd "$srcdir"
  install -d "$pkgdir/opt/kor-workstation" "$pkgdir/usr/bin" \
    "$pkgdir/usr/share/applications" "$pkgdir/usr/share/icons/hicolor/scalable/apps" \
    "$pkgdir/usr/share/licenses/kor-workstation" "$pkgdir/usr/share/doc/kor-workstation"
  install -d "$pkgdir/opt/kor-workstation/core" "$pkgdir/opt/kor-workstation/scripts" "$pkgdir/opt/kor-workstation/web/geodata" "$pkgdir/opt/kor-workstation/web/js"
  install -m644 core/server.py core/window.py core/__init__.py core/mesh.py core/simulation.py "$pkgdir/opt/kor-workstation/core/"
  install -m755 scripts/import-bkg-data.py "$pkgdir/opt/kor-workstation/scripts/"
  install -m644 web/index.html web/styles.css web/app.js "$pkgdir/opt/kor-workstation/web/"
  install -m644 web/js/hud-alerts.js web/js/hud.js web/js/media-hub.js "$pkgdir/opt/kor-workstation/web/js/"
  install -m644 web/geodata/world.geojson "$pkgdir/opt/kor-workstation/web/geodata/world.geojson"
  install -m755 packaging/kor-workstation-launcher.sh "$pkgdir/usr/bin/kor-workstation"
  install -m755 packaging/kor-workstation-stop.sh "$pkgdir/usr/bin/kor-workstation-stop"
  install -m644 packaging/kor-workstation.desktop "$pkgdir/usr/share/applications/kor-workstation.desktop"
  install -m644 packaging/icons/kor-workstation.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/kor-workstation.svg"
  install -m644 LICENSE "$pkgdir/usr/share/licenses/kor-workstation/LICENSE"
  install -m644 README.md EXPORT_SCHEMA.md DECISIONS.md PROJECT_STATUS.md CHANGELOG.md KDE_PLASMA_HUD.md "$pkgdir/usr/share/doc/kor-workstation/"
}