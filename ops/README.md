# ops/ — server-side configuration

These files are not part of the running app. They are the systemd units and
helpers that operators install on the production host.

## Automated PostgreSQL backups

1. As root on the production host, create the secrets dir, the dump
   destination, and copy the env file:

   ```bash
   sudo install -d -o deploy -g deploy -m 0750 /var/backups/media_monitor
   sudo install -d -o root   -g root   -m 0755 /etc/media-monitor
   sudo install -o deploy -g deploy -m 0600 \
       ops/media-monitor-backup.env.example /etc/media-monitor/backup.env
   sudo $EDITOR /etc/media-monitor/backup.env   # set PGPASSWORD=<real value>
   ```

   The real password matches `media_monitor_user` in PostgreSQL (the same value
   in `DATABASE_URL` in `/home/deploy/apps/media-monitor-webapp/.env`).
   `/var/backups/media_monitor` must be writable by the `deploy` user since
   the service unit runs as `User=deploy`.

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

## Off-box backups (v2.5)

Local dumps share the VM's disk, so a lost volume takes both the database and
its backups. To copy dumps off the box, set `BACKUP_REMOTE` in
`/etc/media-monitor/backup.env` to an `rclone` remote; the backup service then
mirrors the dump directory there after each run.

```bash
# 1. Install rclone (Ubuntu): sudo apt-get install -y rclone   (or the official script)
# 2. As the deploy user, configure a remote (Hetzner Storage Box via SFTP,
#    Backblaze B2, S3, etc.):
sudo -u deploy rclone config        # creates a remote, e.g. "hetzner-box"
# 3. Point the backup at it and re-install the unit:
sudo $EDITOR /etc/media-monitor/backup.env    # BACKUP_REMOTE=hetzner-box:media-monitor
sudo install -o root -g root -m 0644 ops/media-monitor-backup.service \
    /etc/systemd/system/media-monitor-backup.service
sudo systemctl daemon-reload
sudo systemctl start media-monitor-backup.service     # test
sudo -u deploy rclone ls hetzner-box:media-monitor    # confirm dumps landed
```

A failed off-box sync marks the unit failed (visible in
`systemctl status media-monitor-backup.service`) but never deletes or corrupts
the local dump, which is written first. Also consider enabling Hetzner's own
VM snapshots in the Cloud Console as a second, independent layer.

## Admin database backup (v2.6)

The app prepares an encrypted whole-DB backup weekly (and on the admin
*Prepare now* button), downloadable from the Dashboard. Setup on the host:

```bash
# 1. Set the passphrase + (optionally) the prepared-file dir in the app .env:
#      BACKUP_PASSPHRASE=<a strong secret — this IS the decryption key>
#      BACKUP_DOWNLOAD_DIR=/var/backups/media_monitor/prepared
sudo $EDITOR /home/deploy/apps/media-monitor-webapp/.env
# 2. Create the deploy-writable prepared dir:
sudo install -d -o deploy -g deploy -m 0750 /var/backups/media_monitor/prepared
sudo systemctl restart media-monitor
```

Decrypt + restore a downloaded backup (on any machine with `cryptography`):

```bash
python3 ops/decrypt_backup.py media_monitor_<ts>.dump.enc   # prompts for BACKUP_PASSPHRASE
pg_restore -h localhost -U media_monitor_user -d media_monitor \
           --clean --if-exists media_monitor_<ts>.dump
```

**Keep `BACKUP_PASSPHRASE` safe** — it is the only key to these files. Losing it
makes existing `*.dump.enc` backups unrecoverable. The on-box systemd daily
`pg_dump` (above) remains as a separate, unencrypted local copy.

## Login / webhook rate limiting (v2.5)

`nginx-rate-limit.conf` documents the `limit_req` snippet applied to
`/api/v1/auth/login` and `/api/v1/webhook/run` to blunt brute-force and
credential-stuffing. It is applied directly in the site's nginx config on the
host (the nginx config is not otherwise tracked in this repo); the file here is
the reference copy. Reload with `sudo nginx -t && sudo systemctl reload nginx`.
