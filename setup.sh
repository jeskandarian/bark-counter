#!/usr/bin/env bash
set -e

INSTALL_DIR=/home/pi/bark-counter
DATA_DIR=/var/lib/bark-counter

echo "=== Bark Counter Setup ==="

# System packages
sudo apt-get update -q
sudo apt-get install -y -q \
  python3 python3-venv python3-pip \
  libportaudio2 portaudio19-dev \
  libsdl2-dev libsdl2-ttf-dev \
  avahi-daemon \
  python3-evdev \
  curl

# Enable I2S for INMP441 mic
BOOT_CFG=/boot/firmware/config.txt
if ! grep -q "dtparam=i2s=on" "$BOOT_CFG"; then
  sudo tee -a "$BOOT_CFG" > /dev/null <<'EOF'

# I2S microphone (INMP441)
dtparam=i2s=on
dtoverlay=i2s-mmap
EOF
fi

# ALSA — route default capture to I2S mic (card 1)
sudo tee /etc/asound.conf > /dev/null <<'EOF'
pcm.i2smic { type hw; card 1; device 0; }
pcm.!default { type asym; capture.pcm "i2smic"; }
EOF

# Waveshare 4" LCD setup — must be done manually once
# Follow: https://www.waveshare.com/wiki/4inch_RPi_LCD_(A)
# The overlay exposes /dev/fb1 (display) and /dev/input/event0 (touch).
if [ ! -f /boot/firmware/overlays/waveshare35a.dtbo ]; then
  echo ""
  echo "WARNING: Waveshare display overlay not installed."
  echo "Run the Waveshare installer, then re-run this script."
  echo "See: https://www.waveshare.com/wiki/4inch_RPi_LCD_(A)"
  echo ""
fi

# Data directories
sudo mkdir -p "$DATA_DIR/recordings"
sudo chown -R pi:pi "$DATA_DIR"

# Python virtualenv + dependencies
cd "$INSTALL_DIR"
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

# Bundle Chart.js locally (no CDN at runtime)
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" \
     -o src/web/static/chart.min.js

# Systemd services
sudo cp systemd/bark-detector.service /etc/systemd/system/
sudo cp systemd/bark-web.service      /etc/systemd/system/
sudo cp systemd/bark-display.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bark-detector bark-web bark-display

# mDNS hostname → bark-counter.local
sudo hostnamectl set-hostname bark-counter
sudo sed -i 's/^#*host-name=.*/host-name=bark-counter/' /etc/avahi/avahi-daemon.conf
sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon

echo ""
echo "=== Done ==="
echo "Reboot to load I2S + display drivers: sudo reboot"
echo "After reboot: sudo systemctl start bark-detector bark-web bark-display"
echo "Dashboard: http://bark-counter.local"
