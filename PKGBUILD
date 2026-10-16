# Maintainer: KOR-NEXUS project
pkgname=kor-workstation
pkgver=1.20.0
pkgrel=1
pkgdesc='Lokale SQLite-Workstation für Kor-Wissen, Projekte, Atlas und RSS'
arch=('any')
license=('custom:KOR-Project')
depends=('python')
optdepends=('chromium: separates App-Fenster im Ein-Klick-Start'
            'xdg-utils: Browser-Fallback, falls Chromium fehlt'
            'firefox: alternativer Browser')
source=("\${pkgname}-\${pkgver}.tar.gz")
sha256sums=('86ce85ab56777ef76ae3169aeec6d4e36054d80efc5139a59a4d8e04eafbd518')

build() {
  cd "$srcdir"
  python -m py_compile core/server.py
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
  install -d "$pkgdir/opt/kor-workstation/core" "$pkgdir/opt/kor-workstation/web/geodata"
  install -m644 core/server.py core/__init__.py "$pkgdir/opt/kor-workstation/core/"
  install -m644 web/index.html web/styles.css web/app.js "$pkgdir/opt/kor-workstation/web/"
  install -m644 web/geodata/world.geojson "$pkgdir/opt/kor-workstation/web/geodata/world.geojson"
  install -m755 packaging/kor-workstation-launcher.sh "$pkgdir/usr/bin/kor-workstation"
  install -m755 packaging/kor-workstation-stop.sh "$pkgdir/usr/bin/kor-workstation-stop"
  install -m644 packaging/kor-workstation.desktop "$pkgdir/usr/share/applications/kor-workstation.desktop"
  install -m644 packaging/icons/kor-workstation.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/kor-workstation.svg"
  install -m644 LICENSE "$pkgdir/usr/share/licenses/kor-workstation/LICENSE"
  install -m644 README.md EXPORT_SCHEMA.md DECISIONS.md PROJECT_STATUS.md CHANGELOG.md "$pkgdir/usr/share/doc/kor-workstation/"
}