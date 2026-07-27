FROM python:3.13-slim

# mysqlclient needs these to build against MySQL's C client library.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev pkg-config build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
