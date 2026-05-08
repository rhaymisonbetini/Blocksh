#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build_appimage.sh — Build Blocksh.AppImage
#
# Usage (from project root):
#   bash packaging/build_appimage.sh
#
# Output:
#   dist/Blocksh-x86_64.AppImage
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
DIST_DIR="${PROJECT_ROOT}/dist"
APPDIR="${DIST_DIR}/Blocksh.AppDir"
TOOLS_DIR="${SCRIPT_DIR}/.tools"
VENV="${PROJECT_ROOT}/.venv"

# ── Colors ─────────────────────────────────────────────────────────────────
BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${BLUE}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Sanity checks ──────────────────────────────────────────────────────────
[[ -f "${PROJECT_ROOT}/run.py" ]] || die "Run this script from the project root or build/ directory."
[[ -d "${VENV}" ]]               || die "Virtual environment not found at ${VENV}. Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   Blocksh AppImage Builder${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Step 1: Install PyInstaller ────────────────────────────────────────────
info "Step 1/5 — Checking PyInstaller..."
source "${VENV}/bin/activate"

if ! python -c "import PyInstaller" 2>/dev/null; then
    info "Installing PyInstaller..."
    pip install --quiet pyinstaller pyinstaller-hooks-contrib
    success "PyInstaller installed."
else
    success "PyInstaller already available."
fi

# ── Step 2: Build with PyInstaller ────────────────────────────────────────
info "Step 2/5 — Building with PyInstaller (this takes a minute)..."
cd "${PROJECT_ROOT}"
rm -rf "${DIST_DIR}/blocksh" build/__pycache__

python -m PyInstaller \
    --distpath "${DIST_DIR}" \
    --workpath "${DIST_DIR}/.pyibuild" \
    --noconfirm \
    "${SCRIPT_DIR}/blocksh.spec"

[[ -f "${DIST_DIR}/blocksh/blocksh" ]] || die "PyInstaller build failed — binary not found."
success "PyInstaller build complete: ${DIST_DIR}/blocksh/"

# ── Step 3: Convert icon SVG → PNG ────────────────────────────────────────
info "Step 3/5 — Converting icon..."
ICON_SVG="${SCRIPT_DIR}/blocksh-icon.svg"
ICON_PNG="${SCRIPT_DIR}/blocksh.png"

if command -v rsvg-convert &>/dev/null; then
    rsvg-convert -w 256 -h 256 "${ICON_SVG}" -o "${ICON_PNG}"
elif command -v inkscape &>/dev/null; then
    inkscape --export-type=png --export-filename="${ICON_PNG}" \
             --export-width=256 --export-height=256 "${ICON_SVG}"
elif command -v convert &>/dev/null; then
    convert -background none -resize 256x256 "${ICON_SVG}" "${ICON_PNG}"
else
    die "No SVG-to-PNG converter found. Install one of: librsvg2-bin, inkscape, imagemagick"
fi
success "Icon converted: ${ICON_PNG}"

# ── Step 4: Assemble AppDir ────────────────────────────────────────────────
info "Step 4/5 — Assembling AppDir..."
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"

# Copy PyInstaller output into AppDir
cp -r "${DIST_DIR}/blocksh/." "${APPDIR}/usr/bin/"

# AppRun — entry point executed by the AppImage runtime
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

# Qt needs to find its platform plugins
export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins/platforms"

# Prevent Qt from looking for system Qt libs
export LD_LIBRARY_PATH="${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH:-}"

exec "${HERE}/usr/bin/blocksh" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# Desktop entry
cp "${SCRIPT_DIR}/blocksh.desktop" "${APPDIR}/blocksh.desktop"

# Icon (root level — required by AppImage spec)
cp "${ICON_PNG}" "${APPDIR}/blocksh.png"

success "AppDir assembled: ${APPDIR}"

# ── Step 5: Download appimagetool and create AppImage ─────────────────────
info "Step 5/5 — Creating AppImage..."
mkdir -p "${TOOLS_DIR}"
APPIMAGETOOL="${TOOLS_DIR}/appimagetool-x86_64.AppImage"

if [[ ! -x "${APPIMAGETOOL}" ]]; then
    info "Downloading appimagetool..."
    curl -fsSL -o "${APPIMAGETOOL}" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "${APPIMAGETOOL}"
    success "appimagetool downloaded."
fi

OUTPUT="${DIST_DIR}/Blocksh-x86_64.AppImage"
ARCH=x86_64 "${APPIMAGETOOL}" --appimage-extract-and-run "${APPDIR}" "${OUTPUT}"

[[ -f "${OUTPUT}" ]] || die "appimagetool failed — AppImage not created."
chmod +x "${OUTPUT}"

# ── Done ───────────────────────────────────────────────────────────────────
SIZE=$(du -sh "${OUTPUT}" | cut -f1)
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}   AppImage ready!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   ${GREEN}File:${NC} ${OUTPUT}"
echo -e "   ${GREEN}Size:${NC} ${SIZE}"
echo ""
echo -e "   Run it:"
echo -e "   ${YELLOW}chmod +x ${OUTPUT##*/}${NC}"
echo -e "   ${YELLOW}./${OUTPUT##*/}${NC}"
echo ""
