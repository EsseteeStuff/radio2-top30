#!/usr/bin/env bash
#
# Bouw en installeer de Flatpak van Top30 (voor de huidige gebruiker).
#
# Eenmalig nodig:
#   flatpak install flathub org.kde.Platform/x86_64/6.11 org.kde.Sdk/x86_64/6.11
#
# Daarna:
#   ./flatpak/build.sh
#
set -euo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HIER/.."

flatpak-builder --user --install --force-clean \
    build/flatpak flatpak/be.serge.Radio2Top30.yaml

echo
echo "Klaar. Starten met:"
echo "    flatpak run be.serge.Radio2Top30"
echo "of via het menu (het item 'Top30')."
