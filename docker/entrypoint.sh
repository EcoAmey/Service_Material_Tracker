#!/bin/sh
set -e

python - <<'EOF'
import os, socket, time

host = os.environ.get('DB_HOST', 'db')
port = int(os.environ.get('DB_PORT', '3306'))
for _ in range(60):
    try:
        socket.create_connection((host, port), timeout=2).close()
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f'Timed out waiting for {host}:{port}')
EOF

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
