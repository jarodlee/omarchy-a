set -euo pipefail
systemctl restart cloudflared-ctb.service
for attempt in $(seq 1 45); do
  if curl -fsS --max-time 2 http://127.0.0.1:37310/ready 2>/dev/null; then
    systemctl is-enabled cloudflared-ctb.service
    systemctl show cloudflared-ctb.service -p ActiveState -p NRestarts -p MemoryCurrent
    exit 0
  fi
  sleep 2
done
exit 1
