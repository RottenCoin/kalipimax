#!/bin/bash
# KaliPiMax — Installation Script
# Raspberry Pi offensive security toolkit with 1.44" LCD HAT
# Supports: Pi Zero 2W, Pi 3, Pi 4 + Waveshare 1.44" LCD HAT
#
# Usage (one-liner — recommended):
#   curl -sL https://raw.githubusercontent.com/RottenCoin/kalipimax/main/install.sh | sudo bash
#
# Usage (git clone):
#   sudo apt install -y git
#   git clone https://github.com/RottenCoin/kalipimax.git
#   cd kalipimax && sudo bash install.sh

set -e
trap 'echo -e "${RED}Error on line $LINENO${NC}"; exit 1' ERR

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_URL="https://github.com/RottenCoin/kalipimax.git"
INSTALL_DIR="/home/kali/kalipimax"

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

echo -e "${CYAN}==========================================================${NC}"
echo -e "${CYAN}        KaliPiMax — Installation${NC}"
echo -e "${CYAN}==========================================================${NC}"

[ "$EUID" -ne 0 ] && { echo -e "${RED}Run as root: sudo bash install.sh${NC}"; exit 1; }

echo -e "${CYAN}Detected:${NC} $(cat /proc/device-tree/model 2>/dev/null || echo 'Unknown')"

# ---------------------------------------------------------------------------
# Bootstrap — detect whether we're inside the repo or piped from curl
# ---------------------------------------------------------------------------

# If BASH_SOURCE is empty or "-", we were piped (curl | sudo bash)
# If BASH_SOURCE points to a dir without main.py, same situation
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]}" ] && [ "${BASH_SOURCE[0]}" != "-" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -n "${SCRIPT_DIR}" ] && [ -f "${SCRIPT_DIR}/main.py" ] && [ -d "${SCRIPT_DIR}/core" ]; then
    # Running from inside the cloned repo
    SOURCE_DIR="${SCRIPT_DIR}"
    echo -e "${CYAN}Source:${NC} ${SOURCE_DIR} (local)"
else
    # Running from curl pipe or standalone download — need to clone
    echo ""
    echo -e "${CYAN}Cloning repository...${NC}"

    # Ensure git is available
    if ! command -v git &>/dev/null; then
        apt update -qq
        apt install -y git
    fi

    SOURCE_DIR="/tmp/kalipimax-src"
    rm -rf "${SOURCE_DIR}"
    git clone --depth 1 "${REPO_URL}" "${SOURCE_DIR}"

    # Validate clone
    if [ ! -f "${SOURCE_DIR}/main.py" ] || [ ! -d "${SOURCE_DIR}/core" ]; then
        echo -e "${RED}Clone failed — main.py or core/ missing in ${SOURCE_DIR}${NC}"
        exit 1
    fi

    echo -e "${CYAN}Source:${NC} ${SOURCE_DIR} (cloned)"
fi

# ---------------------------------------------------------------------------
# Interactive options
# ---------------------------------------------------------------------------
# When piped from curl, stdin is the script itself.
# Redirect reads from /dev/tty (the actual terminal).

echo ""
echo -e "${YELLOW}=== Installation Options ===${NC}"

if [ -t 0 ]; then
    # Normal invocation — stdin is terminal
    TTY_IN="/dev/stdin"
else
    # Piped invocation (curl | sudo bash) — read from terminal directly
    if [ -e /dev/tty ]; then
        TTY_IN="/dev/tty"
    else
        echo -e "${YELLOW}Non-interactive mode — using defaults (all Yes, Metasploit No)${NC}"
        INSTALL_TOOLS=Y; INSTALL_MITM=Y; INSTALL_MSF=N
        INSTALL_USB=Y; INSTALL_SERVICE=Y
        TTY_IN=""
    fi
fi

if [ -n "${TTY_IN}" ]; then
    read -p "Install offensive tools? (nmap, aircrack, tshark, etc.) [Y/n] " -n 1 -r INSTALL_TOOLS < "${TTY_IN}"; echo
    read -p "Install MITM tools? (sslstrip, ettercap, mitmproxy) [Y/n] " -n 1 -r INSTALL_MITM < "${TTY_IN}"; echo
    read -p "Install Metasploit? (~30 min, ~1 GB) [y/N] " -n 1 -r INSTALL_MSF < "${TTY_IN}"; echo
    read -p "Enable USB Gadget support? (dwc2 overlay) [Y/n] " -n 1 -r INSTALL_USB < "${TTY_IN}"; echo
    read -p "Enable auto-start systemd service? [Y/n] " -n 1 -r INSTALL_SERVICE < "${TTY_IN}"; echo
    INSTALL_TOOLS=${INSTALL_TOOLS:-Y}
    INSTALL_MITM=${INSTALL_MITM:-Y}
    INSTALL_MSF=${INSTALL_MSF:-N}
    INSTALL_USB=${INSTALL_USB:-Y}
    INSTALL_SERVICE=${INSTALL_SERVICE:-Y}
fi

echo ""
sleep 1

# ---------------------------------------------------------------------------
# [1/9] Swap — essential on Pi Zero 2 (512 MB RAM)
# ---------------------------------------------------------------------------

echo -e "${CYAN}[1/10] Swap setup...${NC}"
SWAP_SIZE=2048

if [ -f /etc/dphys-swapfile ]; then
    CURRENT=$(grep '^CONF_SWAPSIZE=' /etc/dphys-swapfile | cut -d= -f2)
    if [ "${CURRENT}" != "${SWAP_SIZE}" ]; then
        sed -i "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAP_SIZE}/" /etc/dphys-swapfile
        dphys-swapfile setup && dphys-swapfile swapon
        echo "  ✓ Swap set to ${SWAP_SIZE} MB (was ${CURRENT})"
    else
        echo "  ✓ Swap already ${SWAP_SIZE} MB"
    fi
else
    if [ ! -f /swapfile ] || [ "$(stat -c%s /swapfile 2>/dev/null)" -lt $((SWAP_SIZE * 1024 * 1024)) ]; then
        swapoff -a 2>/dev/null || true
        [ -f /swapfile ] && rm /swapfile
        fallocate -l "${SWAP_SIZE}M" /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        grep -qF '/swapfile' /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
        echo "  ✓ Swap file created (${SWAP_SIZE} MB)"
    else
        echo "  ✓ Swap file already exists"
    fi
fi

# ---------------------------------------------------------------------------
# [2/10] Disk-backed temp directory
# ---------------------------------------------------------------------------
# /tmp is often a tmpfs (RAM-backed, ~256 MB on Pi Zero 2).
# pip wheel builds, Metasploit extraction, and large apt operations
# will exceed that and fail with "No space left on device".
# Fix: create a disk-backed build directory and point everything at it.

echo ""
echo -e "${CYAN}[2/10] Build temp directory...${NC}"

BUILD_TMP="/var/tmp/kalipimax-build"
mkdir -p "${BUILD_TMP}"
chmod 1777 "${BUILD_TMP}"

export TMPDIR="${BUILD_TMP}"
export PIP_TMPDIR="${BUILD_TMP}"
export PIP_CACHE_DIR="${BUILD_TMP}/pip-cache"
mkdir -p "${PIP_CACHE_DIR}"

# If /tmp is a tmpfs and smaller than 512 MB, warn
if mountpoint -q /tmp 2>/dev/null; then
    TMP_SIZE_KB=$(df /tmp | awk 'NR==2 {print $2}')
    if [ "${TMP_SIZE_KB}" -lt 524288 ] 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ /tmp is tmpfs ($(( TMP_SIZE_KB / 1024 )) MB) — redirecting builds to ${BUILD_TMP}${NC}"
    fi
fi

echo "  ✓ Build directory: ${BUILD_TMP}"

# ---------------------------------------------------------------------------
# [3/10] System update
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}[3/10] System update...${NC}"
apt update && apt upgrade -y
echo "  ✓ System updated"

# ---------------------------------------------------------------------------
# [3/9] Core + build dependencies
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}[4/10] Core dependencies...${NC}"

# Runtime
apt install -y \
    python3-full python3-pip python3-dev \
    python3-pil python3-psutil python3-rpi.gpio python3-spidev \
    git wget curl rsync kalipi-config

# Build deps — needed for pip packages that compile on ARM
apt install -y \
    build-essential cmake \
    libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    libfreetype6-dev liblcms2-dev libopenjp2-7 libtiff-dev

echo "  ✓ Core dependencies installed"

# ---------------------------------------------------------------------------
# [5/10] Python packages
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}[5/10] Python packages...${NC}"

# Only install what the codebase actually imports and apt didn't cover
pip3 install --break-system-packages \
    "Pillow>=10.0.0" \
    "psutil>=5.9.0" \
    2>/dev/null || true

echo "  ✓ Python packages installed"

# ---------------------------------------------------------------------------
# [6/10] Boot config — SPI, GPIO pull-ups, USB OTG
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}[6/10] Boot configuration...${NC}"

BOOT_CONFIG="/boot/config.txt"
[ ! -f "$BOOT_CONFIG" ] && BOOT_CONFIG="/boot/firmware/config.txt"

if [ ! -f "$BOOT_CONFIG" ]; then
    echo -e "  ${YELLOW}⚠ Boot config not found — skipping. Configure SPI manually.${NC}"
else
    # SPI (required for LCD)
    grep -q "^dtparam=spi=on" "$BOOT_CONFIG" || {
        echo "dtparam=spi=on" >> "$BOOT_CONFIG"
        echo "  ✓ SPI enabled"
    }

    # GPIO pull-ups for buttons at boot (prevents floating reads before Python starts)
    grep -q "gpio=22,20,16,6,19,5,26,13=pu" "$BOOT_CONFIG" || {
        echo "" >> "$BOOT_CONFIG"
        echo "# KaliPiMax — button GPIO pull-ups" >> "$BOOT_CONFIG"
        echo "gpio=22,20,16,6,19,5,26,13=pu" >> "$BOOT_CONFIG"
        echo "  ✓ GPIO pull-ups configured"
    }

    # USB OTG (required for USB gadget mode)
    if [[ $INSTALL_USB =~ ^[Yy]$ ]]; then
        grep -q "^dtoverlay=dwc2" "$BOOT_CONFIG" || {
            echo "dtoverlay=dwc2" >> "$BOOT_CONFIG"
            echo "  ✓ dwc2 overlay enabled"
        }
        grep -q "libcomposite" /etc/modules || {
            echo "libcomposite" >> /etc/modules
            echo "  ✓ libcomposite added to /etc/modules"
        }
    fi

    echo "  ✓ Boot config done"
fi

# ---------------------------------------------------------------------------
# [7/10] Offensive tools
# ---------------------------------------------------------------------------

echo ""
if [[ $INSTALL_TOOLS =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}[7/10] Offensive tools...${NC}"

    apt install -y \
        nmap masscan hping3 \
        netcat-traditional socat \
        tcpdump tshark wireshark-common \
        dnsutils net-tools wireless-tools iw ethtool \
        aircrack-ng macchanger \
        iperf3

    # Responder — apt package often missing on Kali ARM; git clone is reliable
    if [ ! -d "/opt/Responder" ]; then
        echo "  Installing Responder from git..."
        cd /opt && git clone --depth 1 https://github.com/lgandx/Responder.git
        chmod +x /opt/Responder/Responder.py
        ln -sf /opt/Responder/Responder.py /usr/local/bin/responder
        echo "  ✓ Responder installed to /opt/Responder"
    else
        echo "  ✓ Responder already present"
    fi

    echo "  ✓ Offensive tools installed"
else
    echo -e "${YELLOW}[7/10] Skipped offensive tools${NC}"
fi

# ---------------------------------------------------------------------------
# [8/10] MITM tools (separate — large and not always needed)
# ---------------------------------------------------------------------------

echo ""
if [[ $INSTALL_MITM =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}[8/10] MITM tools...${NC}"

    apt install -y \
        dsniff \
        ettercap-text-only \
        mitmproxy \
        2>/dev/null || true

    # sslstrip — may not be in repos; best-effort
    apt install -y sslstrip 2>/dev/null || {
        echo -e "  ${YELLOW}⚠ sslstrip not in repos — install manually if needed${NC}"
    }

    echo "  ✓ MITM tools installed"
else
    echo -e "${YELLOW}[8/10] Skipped MITM tools${NC}"
fi

# ---------------------------------------------------------------------------
# [9/10] Metasploit (optional — huge, slow on Zero)
# ---------------------------------------------------------------------------

echo ""
if [[ $INSTALL_MSF =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}[9/10] Metasploit (this will take a while)...${NC}"

    if command -v msfconsole &>/dev/null; then
        echo "  ✓ Metasploit already installed"
    else
        # Download to disk-backed dir, not /tmp (tmpfs too small for MSF)
        curl -s https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > "${BUILD_TMP}/msfinstall"
        chmod 755 "${BUILD_TMP}/msfinstall"
        TMPDIR="${BUILD_TMP}" "${BUILD_TMP}/msfinstall"
        rm -f "${BUILD_TMP}/msfinstall"
        echo "  ✓ Metasploit installed"
    fi
else
    echo -e "${YELLOW}[9/10] Skipped Metasploit${NC}"
fi

# ---------------------------------------------------------------------------
# [10/10] Install KaliPiMax files
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}[10/10] Installing KaliPiMax v2...${NC}"

mkdir -p "${INSTALL_DIR}"

# Copy project files, excluding dev/build artefacts
rsync -a \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'tests' \
    --exclude '.gitignore' \
    --exclude 'logs' \
    "${SOURCE_DIR}/" "${INSTALL_DIR}/"

# Create loot directories
for subdir in nmap responder mitm deauth wifi shells captures; do
    mkdir -p "${INSTALL_DIR}/loot/${subdir}"
done

# Create logs directory
mkdir -p "${INSTALL_DIR}/logs"

# Ownership
chown -R kali:kali "${INSTALL_DIR}"

# Make main.py executable
chmod +x "${INSTALL_DIR}/main.py"

echo "  ✓ Files installed to ${INSTALL_DIR}"

# ---------------------------------------------------------------------------
# Systemd service
# ---------------------------------------------------------------------------

if [[ $INSTALL_SERVICE =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${CYAN}Creating systemd service...${NC}"

    cat > /etc/systemd/system/kalipimax.service << EOF
[Unit]
Description=KaliPiMax Offensive Security Toolkit
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/main.py
Restart=on-failure
RestartSec=5
# Graceful shutdown — allows GPIO cleanup
KillSignal=SIGTERM
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable kalipimax
    echo "  ✓ Service enabled (kalipimax.service)"
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

apt clean
apt autoremove -y 2>/dev/null || true

# Remove disk-backed build directory
if [ -d "${BUILD_TMP}" ]; then
    rm -rf "${BUILD_TMP}"
    echo "  ✓ Build temp cleaned (${BUILD_TMP})"
fi

# Remove temp clone if we created one
if [ "${SOURCE_DIR}" = "/tmp/kalipimax-src" ] && [ -d "${SOURCE_DIR}" ]; then
    rm -rf "${SOURCE_DIR}"
    echo "  ✓ Temp clone cleaned"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo -e "${GREEN}==========================================================${NC}"
echo -e "${GREEN}           Installation Complete${NC}"
echo -e "${GREEN}==========================================================${NC}"
echo ""
echo -e "  ${CYAN}Location:${NC}  ${INSTALL_DIR}"
echo -e "  ${CYAN}Loot:${NC}      ${INSTALL_DIR}/loot/"
echo -e "  ${CYAN}Logs:${NC}      ${INSTALL_DIR}/logs/"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo "    1. sudo reboot          (required if SPI/dwc2 were just enabled)"
echo "    2. sudo systemctl start kalipimax"
echo "    — or run manually: cd ${INSTALL_DIR} && sudo python3 main.py"
echo ""
echo -e "  ${CYAN}Controls:${NC}"
echo "    KEY1 = Backlight   KEY2 = Next mode   KEY3 = Action / Cancel"
echo "    Joystick = Navigate   Press = Execute"
echo ""
echo -e "  ${CYAN}Logs:${NC}  sudo journalctl -u kalipimax -f"
echo ""

# Report what was installed
echo -e "  ${CYAN}Installed components:${NC}"
echo "    ✓ Core + Python + SPI + GPIO pull-ups + swap (${SWAP_SIZE} MB)"
[[ $INSTALL_TOOLS =~ ^[Yy]$ ]]   && echo "    ✓ Offensive tools (nmap, aircrack, tshark, Responder, ...)"
[[ $INSTALL_MITM =~ ^[Yy]$ ]]    && echo "    ✓ MITM tools (dsniff, ettercap, mitmproxy, sslstrip)"
[[ $INSTALL_MSF =~ ^[Yy]$ ]]     && echo "    ✓ Metasploit"
[[ $INSTALL_USB =~ ^[Yy]$ ]]     && echo "    ✓ USB gadget (dwc2 + libcomposite)"
[[ $INSTALL_SERVICE =~ ^[Yy]$ ]] && echo "    ✓ Auto-start service"

echo ""
echo -e "${RED}⚠  Legal: Authorised networks only. Unauthorised use is illegal.${NC}"
echo ""
