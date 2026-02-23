import pickle
import time

fs_path = '/home/cowrie/cowrie/src/cowrie/data/fs.pickle'

with open(fs_path, 'rb') as f:
    fs = pickle.load(f)

def add_entry(node, path, is_dir=False, size=0):
    parts = path.strip('/').split('/')
    current = node
    for part in parts:
        found = False
        for entry in current[7]:
            if entry[0] == part:
                current = entry
                found = True
                break
        if not found:
            mode = 16877 if is_dir else 33188
            new_entry = [part, 1 if is_dir else 2, 0, 0, size, mode, int(time.time()), [], None, None]
            current[7].append(new_entry)
            current = new_entry

# Fake web application
add_entry(fs, '/var/www', is_dir=True)
add_entry(fs, '/var/www/html', is_dir=True)
add_entry(fs, '/var/www/html/app', is_dir=True)
add_entry(fs, '/var/www/html/app/config', is_dir=True)
add_entry(fs, '/var/www/html/app/uploads', is_dir=True)
add_entry(fs, '/var/www/html/app/logs', is_dir=True)
add_entry(fs, '/var/www/html/app/config/database.php', size=1024)
add_entry(fs, '/var/www/html/app/config/.env', size=256)
add_entry(fs, '/var/www/html/app/logs/error.log', size=4096)

# Fake employee home directories
add_entry(fs, '/home/jsmith', is_dir=True)
add_entry(fs, '/home/jsmith/.ssh', is_dir=True)
add_entry(fs, '/home/jsmith/.ssh/authorized_keys', size=512)
add_entry(fs, '/home/jsmith/.bash_history', size=2048)
add_entry(fs, '/home/mlopez', is_dir=True)
add_entry(fs, '/home/mlopez/.ssh', is_dir=True)
add_entry(fs, '/home/mlopez/.ssh/authorized_keys', size=512)
add_entry(fs, '/home/admin', is_dir=True)
add_entry(fs, '/home/admin/.ssh', is_dir=True)
add_entry(fs, '/home/admin/.ssh/authorized_keys', size=512)
add_entry(fs, '/home/deploy', is_dir=True)
add_entry(fs, '/home/deploy/.ssh', is_dir=True)
add_entry(fs, '/home/deploy/.ssh/authorized_keys', size=512)

# Fake internal app
add_entry(fs, '/opt/app', is_dir=True)
add_entry(fs, '/opt/app/config', is_dir=True)
add_entry(fs, '/opt/app/config/settings.py', size=2048)
add_entry(fs, '/opt/app/config/.env', size=256)
add_entry(fs, '/opt/app/logs', is_dir=True)
add_entry(fs, '/opt/app/logs/app.log', size=8192)

with open(fs_path, 'wb') as f:
    pickle.dump(fs, f)

print('Filesystem updated successfully.')
