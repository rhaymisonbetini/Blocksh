#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Blocksh — one-line installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rhaymisonbetini/Blocksh/main/install.sh | bash
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

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${BLUE}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   Installing Blocksh${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

mkdir -p "${INSTALL_DIR}" "${ICON_DIR}" "${DESKTOP_DIR}"

info "Downloading Blocksh AppImage..."
curl -fsSL --progress-bar -o "${APPIMAGE}" "${APPIMAGE_URL}"
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
echo -e "${GREEN}   Blocksh installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   Launch from your app menu  ${YELLOW}(search: Blocksh)${NC}"
echo -e "   Or run directly:           ${YELLOW}${APPIMAGE}${NC}"
echo ""
echo -e "   To uninstall:"
echo -e "   ${YELLOW}rm ${APPIMAGE} ${ICON_DIR}/blocksh.png ${DESKTOP_DIR}/blocksh.desktop${NC}"
echo ""
