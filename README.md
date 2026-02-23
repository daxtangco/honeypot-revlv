# Cowrie SSH/Telnet Honeypot

A medium-interaction SSH and Telnet honeypot built with [Cowrie](https://github.com/cowrie/cowrie). Logs all attacker activity — credentials, commands, and file downloads — to PostgreSQL and JSON.

---

## What It Does

- Emulates a fake Linux shell over SSH and Telnet on standard ports 22/23 via port redirection
- Logs every login attempt, command typed, and file downloaded by attackers
- Stores all captured data in a PostgreSQL database
- Runs as an unprivileged system user with auto-start via systemd

---

## Repository Contents

| File | Description |
|---|---|
| `cowrie.cfg` | Cowrie configuration (ports, PostgreSQL connection) |
| `userdb.txt` | Controls which credentials grant access to the fake shell |
| `cowrie.service` | Systemd service for auto-start on boot |
| `cowrie-logrotate` | Daily log rotation with 7-day retention |
| `postgresql.py` | Patched Cowrie PostgreSQL output plugin |
| `add_fs.py` | Script to inject a realistic corporate fake filesystem into Cowrie |

---

## Prerequisites

- Ubuntu 20.04+
- Python 3.8+
- PostgreSQL 12+
- A non-standard port chosen for your real SSH access (e.g. 22222)

---

## Setup

### 1. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip \
  libssl-dev libffi-dev build-essential libpython3-dev \
  python3-minimal authbind postgresql postgresql-contrib libpq-dev
```

### 2. Create a Dedicated `cowrie` User

```bash
sudo adduser --disabled-password --gecos "" cowrie
```

### 3. Clone and Install Cowrie

```bash
sudo su - cowrie
git clone https://github.com/cowrie/cowrie.git ~/cowrie
cd ~/cowrie
python3 -m venv cowrie-env
source cowrie-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 4. Apply Config Files

```bash
cp cowrie.cfg /home/cowrie/cowrie/etc/cowrie.cfg
cp userdb.txt /home/cowrie/cowrie/etc/userdb.txt
cp postgresql.py /home/cowrie/cowrie/src/cowrie/output/postgresql.py
```

Edit `cowrie.cfg` and replace `<your-password>` with your chosen password:

```ini
[ssh]
enabled = true
listen_endpoints = tcp:2222:interface=0.0.0.0

[telnet]
enabled = true
listen_endpoints = tcp:2223:interface=0.0.0.0

[output_jsonlog]
enabled = true

[output_postgresql]
enabled = true
host = 127.0.0.1
database = cowrie
username = cowrie
password = <your-password>
port = 5432
```

> **Note:** Cowrie binds internally to ports 2222 and 2223. The iptables rules in Step 7 redirect public ports 22 and 23 to these internal ports. From the outside, attackers hit standard port 22 and land directly in the honeypot — it looks exactly like a real SSH server.

Edit `userdb.txt` and replace `<your-password>` with the same password:

```
root:x:<your-password>
root:x:!*
*:x:!*
```

This allows only `root` with your chosen password to access the fake shell. All other credentials are denied.

Restrict the file permissions:

```bash
chmod 600 /home/cowrie/cowrie/etc/userdb.txt
```

### 5. Set Up PostgreSQL

```bash
sudo -u postgres psql
```

```sql
SET password_encryption = 'scram-sha-256';
CREATE USER cowrie WITH PASSWORD '<your-password>';
CREATE DATABASE cowrie OWNER cowrie;
\q
```

Import the schema:

```bash
psql -U cowrie -h 127.0.0.1 -d cowrie -f /home/cowrie/cowrie/docs/sql/postgres.sql
```

Add this line to `/etc/postgresql/*/main/pg_hba.conf`:

```
host    cowrie    cowrie    127.0.0.1/32    scram-sha-256
```

Reload PostgreSQL:

```bash
sudo systemctl reload postgresql
```

### 6. Move Real SSH to a Non-Standard Port

Edit `/etc/ssh/sshd_config` and change:
```
#Port 22
```
to:
```
Port 22222
```

Open the new port in UFW (if active):
```bash
ufw allow 22222/tcp
```

**Ubuntu 24+ only — disable SSH socket activation:**

On Ubuntu 24+, SSH uses socket-based activation which overrides the port in `sshd_config`. Disable it so the service respects your config:
```bash
systemctl disable --now ssh.socket
systemctl enable --now ssh.service
systemctl restart ssh
```

Verify SSH is listening on 22222:
```bash
ss -tlnp | grep sshd
```

> Open a **new terminal** and confirm you can connect on port 22222 before continuing. Do not close your current session until verified.

Once confirmed, kill the old SSH instance still on port 22 (use the PID from `ss -tlnp`):
```bash
kill <old-sshd-pid>
```

### 7. Redirect Ports 22/23 to Cowrie

```bash
iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
iptables -t nat -A PREROUTING -p tcp --dport 23 -j REDIRECT --to-port 2223
apt install iptables-persistent
netfilter-persistent save
```

If UFW is active, remove the old port 22 rule:
```bash
ufw delete allow 22/tcp
```

### 8. Install Systemd Service

```bash
sudo cp cowrie.service /etc/systemd/system/cowrie.service
sudo systemctl daemon-reload
sudo systemctl enable cowrie
sudo systemctl start cowrie
```

### 9. Set Up Log Rotation

```bash
sudo cp cowrie-logrotate /etc/logrotate.d/cowrie
```

Add cleanup cron jobs (run `crontab -e` as the `cowrie` user):

```
0 3 * * * find /home/cowrie/cowrie/var/lib/cowrie/downloads/ -type f -mtime +30 -delete
0 4 * * * find /home/cowrie/cowrie/var/lib/cowrie/tty/ -type f -mtime +30 -delete
```

### 10. Inject a Fake Corporate Filesystem (Optional)

By default Cowrie ships with a basic Linux filesystem. `add_fs.py` extends it with realistic-looking corporate directories to make the honeypot more convincing to attackers.

Entries added:

| Path | Type |
|---|---|
| `/var/www/html/app/` | Web application root |
| `/var/www/html/app/config/database.php` | Database credentials file (bait) |
| `/var/www/html/app/config/.env` | Environment config (bait) |
| `/var/www/html/app/logs/error.log` | Application error log |
| `/home/jsmith/`, `/home/mlopez/`, `/home/admin/`, `/home/deploy/` | Fake employee home directories |
| `/home/*/.ssh/authorized_keys` | SSH key files (bait) |
| `/opt/app/config/settings.py` | Internal app config (bait) |
| `/opt/app/logs/app.log` | Internal app log |

Copy the script to the server and run it as root:

```bash
scp add_fs.py root@<your-server-ip>:/tmp/add_fs.py
ssh root@<your-server-ip> "cd /home/cowrie/cowrie && cowrie-env/bin/python3 /tmp/add_fs.py && chown cowrie:cowrie src/cowrie/data/fs.pickle && systemctl restart cowrie"
```

Verify it worked by connecting to the honeypot and browsing the filesystem:

```bash
ssh root@<your-server-ip>
ls /home
ls /var/www/html/app
ls /opt/app
```

---

## Verification

**Check the service is running:**

```bash
systemctl status cowrie --no-pager
```

**Check ports are listening:**

```bash
ss -tlnp | grep -E '(2222|2223)'
```

**Connect to the honeypot to test it:**

If you previously connected to this server on port 22, clear the old host key first:
```bash
ssh-keygen -R <your-server-ip>
```

Then connect — port 22 now redirects to Cowrie:
```bash
ssh root@<your-server-ip>
```

Enter your password when prompted and you will land in Cowrie's fake shell — nothing executed here affects the real server.

**Connect to the real server:**

```bash
ssh root@<your-server-ip> -p 22222
```

---

## Querying Captured Data

Replace `<your-server-ip>` and `<your-password>` in all commands below.

**Recent login attempts:**

```bash
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT timestamp, username, password, success FROM auth ORDER BY timestamp DESC LIMIT 10;'"
```

**Recent sessions:**

```bash
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT id, starttime, ip, endtime FROM sessions ORDER BY starttime DESC LIMIT 10;'"
```

**Commands executed by attackers:**

```bash
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT s.ip, i.timestamp, i.input FROM input i JOIN sessions s ON i.session = s.id ORDER BY i.timestamp DESC LIMIT 20;'"
```

**Files downloaded by attackers:**

```bash
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT session, timestamp, url, shasum FROM downloads ORDER BY timestamp DESC LIMIT 10;'"
```

**Everything from one session:**

Each session has a unique hex ID (e.g. `a7117fe84ba5`) visible in the `sessions` table. Use it to trace all activity from a single connection:

```bash
# Auth attempts
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT timestamp, username, password, success FROM auth WHERE session = '\''<session-id>'\'' ORDER BY timestamp;'"

# Commands typed
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT timestamp, input FROM input WHERE session = '\''<session-id>'\'' ORDER BY timestamp;'"

# Files downloaded
ssh root@<your-server-ip> "PGPASSWORD='<your-password>' psql -U cowrie -h 127.0.0.1 -d cowrie -c 'SELECT timestamp, url, shasum FROM downloads WHERE session = '\''<session-id>'\'' ORDER BY timestamp;'"
```

**Monitor logs in real time:**

```bash
ssh root@<your-server-ip> "tail -f /home/cowrie/cowrie/var/log/cowrie/cowrie.json"
```

---

## File Paths Reference

| File/Directory | Path |
|---|---|
| Cowrie install | `/home/cowrie/cowrie/` |
| Config file | `/home/cowrie/cowrie/etc/cowrie.cfg` |
| Credential auth | `/home/cowrie/cowrie/etc/userdb.txt` |
| Fake filesystem | `/home/cowrie/cowrie/src/cowrie/data/fs.pickle` |
| JSON logs | `/home/cowrie/cowrie/var/log/cowrie/` |
| Output plugins | `/home/cowrie/cowrie/src/cowrie/output/` |
| Downloaded files | `/home/cowrie/cowrie/var/lib/cowrie/downloads/` |
| TTY logs | `/home/cowrie/cowrie/var/lib/cowrie/tty/` |
| PostgreSQL schema | `/home/cowrie/cowrie/docs/sql/postgres.sql` |
| Systemd service | `/etc/systemd/system/cowrie.service` |
| Logrotate config | `/etc/logrotate.d/cowrie` |
| pg_hba.conf | `/etc/postgresql/*/main/pg_hba.conf` |
