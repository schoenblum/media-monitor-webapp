# ops/ — server-side configuration

These files are not part of the running app. They are the systemd units and
helpers that operators install on the production host.

## Automated PostgreSQL backups

1. As root on the production host, create the secrets dir and copy the env file:

   ```bash
   sudo install -d -o root -g root -m 0755 /etc/media-monitor
   sudo install -o deploy -g deploy -m 0600 \
       ops/media-monitor-backup.env.example /etc/media-monitor/backup.env
   sudo $EDITOR /etc/media-monitor/backup.env   # set PGPASSWORD=<real value>
   ```

   The real password matches `media_monitor_user` in PostgreSQL (the same value
   in `DATABASE_URL` in `/home/deploy/apps/media-monitor-webapp/.env`).

2. Install the unit + timer:

   ```bash
   sudo install -o root -g root -m 0644 ops/media-monitor-backup.service \
       /etc/systemd/system/media-monitor-backup.service
   sudo install -o root -g root -m 0644 ops/media-monitor-backup.timer \
       /etc/systemd/system/media-monitor-backup.timer
   sudo systemctl daemon-reload
   sudo systemctl enable --now media-monitor-backup.timer
   ```

3. Verify:

   ```bash
   systemctl status media-monitor-backup.timer
   systemctl list-timers --all | grep media-monitor
   sudo systemctl start media-monitor-backup.service   # force one immediately
   ls -lh /var/backups/media_monitor/
   ```

## Restore

```bash
sudo -u deploy bash -c '
  PGPASSWORD="$(grep ^PGPASSWORD /etc/media-monitor/backup.env | cut -d= -f2-)" \
  pg_restore -h localhost -U media_monitor_user -d media_monitor \
             --clean --if-exists \
             /var/backups/media_monitor/media_monitor_YYYYMMDD.dump
'
```

The backup directory keeps the **14 most recent** daily dumps; older files are
pruned by the service unit.
