set -euo pipefail
test "$(uname -m)" = aarch64
install -d -m 755 /opt/cloudflared/2026.10.7
cd /opt/cloudflared/2026.10.7
curl -fL --connect-timeout 10 --max-time 150 -o cloudflared.part https://github.com/cloudflare/cloudflared/releases/download/2026.10.7/cloudflared-linux-arm64
echo '3df43aedc9ff291d1735b5cb576cb97e0b157488796db2e32b28aecabb445775  cloudflared.part' | sha256sum -c -
chmod 755 cloudflared.part
mv cloudflared.part cloudflared
./cloudflared --version
ln -sfn /opt/cloudflared/2026.10.7/cloudflared /usr/local/bin/cloudflared
getent passwd cloudflared-ctb >/dev/null || useradd --system --no-create-home --shell /usr/bin/nologin cloudflared-ctb
install -d -o root -g cloudflared-ctb -m 750 /etc/cloudflared-ctb
echo CLOUDFLARED_INSTALLED_NOT_ROUTED
