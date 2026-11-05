set -euo pipefail
systemd-analyze verify /etc/systemd/system/omarchy-home.service
systemctl daemon-reload
systemctl enable --now omarchy-home.service
for attempt in $(seq 1 10); do
 if curl -fsS --max-time 2 http://127.0.0.1/health; then
  curl -fsS --max-time 5 http://127.0.0.1/api/status
  systemctl show omarchy-home -p ActiveState -p MemoryCurrent -p NRestarts
  exit 0
 fi
 sleep 1
done
exit 1
