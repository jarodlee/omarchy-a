set -euo pipefail
test -f /opt/cn-math-taxonomy/releases/276b88c4-accounts-v1/account.html
systemd-analyze verify /etc/systemd/system/cn-math-taxonomy.service /etc/systemd/system/cn-math-backup.service /etc/systemd/system/cn-math-backup.timer
ln -sfn /opt/cn-math-taxonomy/releases/276b88c4-accounts-v1 /opt/cn-math-taxonomy/current
systemctl daemon-reload
systemctl restart cn-math-taxonomy.service
for attempt in $(seq 1 15); do
 if curl -fsS --max-time 2 http://127.0.0.1:3002/api/health; then
  systemctl enable --now cn-math-backup.timer
  systemctl start cn-math-backup.service
  systemctl show cn-math-taxonomy -p ActiveState -p MemoryCurrent -p NRestarts
  exit 0
 fi
 sleep 1
done
exit 1
