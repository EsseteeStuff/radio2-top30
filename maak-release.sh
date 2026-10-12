#!/usr/bin/env bash
# Copyright (C) 2026 EsseteeStuff
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Een nieuwe release maken in drie stappen: tag, release, builds.
#
#   ./maak-release.sh 1.1                  # alles
#   ./maak-release.sh 1.1 --nee-builds      # alleen tag + release
#   ./maak-release.sh 1.1 --oefen           # droge proef
#
# De build-workflows (Linux, macOS, Windows) staan op handmatig; die worden
# hier vandaan gestart met de release-tag erbij. De release wordt eerst
# aangemaakt door `gh release create`, de workflows uploaden hun pakketten
# erop. Eerst push je jouw wijzigingen, daarna draai je dit script.
set -euo pipefail

VERSIE=""
BUILDS=1
OEFEN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --nee-builds) BUILDS=0; shift ;;
        --oefen) OEFEN=1; shift ;;
        -h|--help) sed -n '18,22p' "$0" | cut -c3- ; exit 0 ;;
        *) [[ -z "$VERSIE" ]] && VERSIE="$1" || { echo "Fout: onbekend argument: $1"; exit 1; }; shift ;;
    esac
done

[[ -n "$VERSIE" ]] || { echo "Fout: geef een versie mee, bijv.: ./maak-release.sh 1.1"; exit 1; }
TAG="v${VERSIE#v}"
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo "Fout: ongeldige versie: $TAG (bijv. 1.1 of 1.2.0)"; exit 1; }

# ---------------------------------------------------------------- controles
cd "$(dirname "$0")"
[[ -d .git ]] || { echo "Fout: geen git-repo"; exit 1; }

doet() {  # 1=commando, rest=argumenten
    if [[ $OEFEN -eq 1 ]]; then
        echo "   [droge proef] $*"
    else
        "$@"
    fi
}

if [[ $OEFEN -ne 1 ]]; then
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Fout: de werkmap is niet schoon; commit of stash eerst."
        exit 1
    fi
    if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
        echo "Fout: de tag $TAG bestaat al."
        exit 1
    fi
    if ! gh auth status >/dev/null 2>&1; then
        echo "Fout: niet ingelogd bij GitHub; doe eerst: gh auth login"
        exit 1
    fi
fi

# ---------------------------------------------------------------- uitvoeren
echo "Release $TAG maken …"
doet git tag -a "$TAG" -m "Top30 ${TAG#v}"
doet git push origin "$TAG"
doet gh release create "$TAG" --title "Top30 ${TAG#v}" --generate-notes
echo "   (de release is eerst leeg; de builds zetten de pakketten erop)"

if [[ $BUILDS -eq 1 ]]; then
    echo "De drie builds starten …"
    for wf in linux-packages macos-build windows-build; do
        doet gh workflow run "$wf.yml" --ref "$TAG" -f release_tag="$TAG"
    done
    if [[ $OEFEN -eq 0 ]]; then
        REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
        echo "   volg ze op: https://github.com/$REPO/actions"
    fi
else
    echo "   (geen builds gestart; draai ze later handmatig met de "
    echo "    release_tag-invoer op GitHub → Actions)"
fi

echo "Klaar."