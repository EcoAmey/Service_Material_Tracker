FROM mysql:8.0

# Seeds this image with the current fault_tracker data on first container
# start (official MySQL image auto-runs *.sql files in this directory
# against an empty data dir) -- existing data is carried forward, not wiped.
COPY 01-fault_tracker.sql /docker-entrypoint-initdb.d/
