#!/bin/bash
# install.sh — Lädt xos, xoso, xosb vom neuesten GitHub Release
# Verwendung: ./install.sh

set -e

REPO="xium-ai/releases"
BASE_URL="https://github.com/${REPO}/releases/latest/download"

# Plattform erkennen
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Darwin)
    SUFFIX="macos"
    ;;
  Linux)
    case "$ARCH" in
      x86_64)  SUFFIX="linux_amd64" ;;
      aarch64) SUFFIX="linux_arm64" ;;
      *)       echo "❌ Unbekannte Architektur: $ARCH"; exit 1 ;;
    esac
    ;;
  *)
    echo "❌ Unbekanntes Betriebssystem: $OS"
    echo "   Windows: xos_windows_amd64.exe, xoso_windows_amd64.exe, xosb_windows_amd64.exe"
    echo "   manuell herunterladen von: https://github.com/${REPO}/releases/latest"
    exit 1
    ;;
esac

echo "⬇️  Lade Binaries für ${OS}/${ARCH}..."

for BIN in xos xoso xosb; do
  FILE="${BIN}_${SUFFIX}"
  echo "   ${FILE}"
  curl -fsSL "${BASE_URL}/${FILE}" -o "${BIN}"
  chmod +x "${BIN}"
done

echo ""
echo "✅ Installiert: xos, xoso, xosb"
echo ""
echo "Weiter mit:"
echo "  make infra"
