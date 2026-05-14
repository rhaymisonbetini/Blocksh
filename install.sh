#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Blocksh — one-line installer / updater
#
# Install:
#   curl -fsSL https://raw.githubusercontent.com/rhaymisonbetini/Blocksh/main/install.sh | bash
#
# Update:
#   curl -fsSL https://raw.githubusercontent.com/rhaymisonbetini/Blocksh/main/install.sh | bash -s -- --update
#
# What it does:
#   1. Downloads Blocksh-x86_64.AppImage to ~/.local/bin/
#   2. Downloads the app icon to ~/.local/share/icons/
#   3. Creates a .desktop entry so Blocksh appears in the system app menu
# ---------------------------------------------------------------------------
set -euo pipefail

RELEASE_URL="https://github.com/rhaymisonbetini/Blocksh/releases/latest/download"
APPIMAGE_URL="${RELEASE_URL}/Blocksh-x86_64.AppImage"
ICON_URL="${RELEASE_URL}/blocksh.png"

INSTALL_DIR="${HOME}/.local/bin"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="${HOME}/.local/share/applications"
APPIMAGE="${INSTALL_DIR}/Blocksh.AppImage"

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${BLUE}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Mode: install vs update ────────────────────────────────────────────────
UPDATE_MODE=false
for arg in "${@:-}"; do
    [[ "${arg}" == "--update" ]] && UPDATE_MODE=true
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if $UPDATE_MODE; then
    echo -e "${BLUE}   Updating Blocksh${NC}"
else
    echo -e "${BLUE}   Installing Blocksh${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Skip if already up-to-date (update mode only) ─────────────────────────
if $UPDATE_MODE && [[ -f "${APPIMAGE}" ]]; then
    info "Checking for updates..."
    CHECKSUM_FILE="$(mktemp)"
    curl -fsSL -o "${CHECKSUM_FILE}" "${RELEASE_URL}/Blocksh-x86_64.AppImage.sha256"
    REMOTE_HASH=$(awk '{print $1}' "${CHECKSUM_FILE}")
    rm -f "${CHECKSUM_FILE}"
    LOCAL_HASH=$(sha256sum "${APPIMAGE}" | awk '{print $1}')
    if [[ "${LOCAL_HASH}" == "${REMOTE_HASH}" ]]; then
        success "Already up-to-date. Nothing to do."
        echo ""
        exit 0
    fi
    info "Update available — downloading new version..."
fi

mkdir -p "${INSTALL_DIR}" "${ICON_DIR}" "${DESKTOP_DIR}"

# ── Download ───────────────────────────────────────────────────────────────
info "Downloading Blocksh AppImage..."
APPIMAGE_TMP="$(mktemp)"
curl -fsSL --progress-bar -o "${APPIMAGE_TMP}" "${APPIMAGE_URL}"

# ── Verify checksum ────────────────────────────────────────────────────────
info "Verifying checksum..."
CHECKSUM_FILE="$(mktemp)"
curl -fsSL -o "${CHECKSUM_FILE}" "${RELEASE_URL}/Blocksh-x86_64.AppImage.sha256"
EXPECTED=$(awk '{print $1}' "${CHECKSUM_FILE}")
ACTUAL=$(sha256sum "${APPIMAGE_TMP}" | awk '{print $1}')
rm -f "${CHECKSUM_FILE}"
if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
    rm -f "${APPIMAGE_TMP}"
    die "Checksum mismatch — aborting installation."
fi
success "Checksum verified."

# ── Install ────────────────────────────────────────────────────────────────
mv "${APPIMAGE_TMP}" "${APPIMAGE}"
chmod +x "${APPIMAGE}"
success "AppImage saved to ${APPIMAGE}"

info "Downloading icon..."
curl -fsSL -o "${ICON_DIR}/blocksh.png" "${ICON_URL}"
success "Icon saved."

info "Creating desktop entry..."
cat > "${DESKTOP_DIR}/blocksh.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Blocksh
GenericName=Terminal Emulator
Comment=Block-based terminal emulator with full PTY support
Exec=${APPIMAGE}
Icon=blocksh
Categories=System;TerminalEmulator;
Terminal=false
StartupNotify=true
Keywords=terminal;shell;pty;block;
DESKTOP

# Refresh desktop database and icon cache
update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if $UPDATE_MODE; then
    echo -e "${GREEN}   Blocksh updated successfully!${NC}"
else
    echo -e "${GREEN}   Blocksh installed successfully!${NC}"
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   Launch from your app menu  ${YELLOW}(search: Blocksh)${NC}"
echo -e "   Or run directly:           ${YELLOW}${APPIMAGE}${NC}"
echo ""
echo -e "   To update:   ${YELLOW}curl -fsSL https://raw.githubusercontent.com/rhaymisonbetini/Blocksh/main/install.sh | bash -s -- --update${NC}"
echo -e "   To uninstall: ${YELLOW}rm ${APPIMAGE} ${ICON_DIR}/blocksh.png ${DESKTOP_DIR}/blocksh.desktop${NC}"
echo ""
