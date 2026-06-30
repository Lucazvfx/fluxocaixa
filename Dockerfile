<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> c4af594019c9ef580ae7c415f45c042723666157
services:
  - type: web
    name: fluxocaixa
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: /bin/sh -c "/opt/render/project/src/.venv/bin/gunicorn app:app --bind 0.0.0.0:$PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: fluxocaixa-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
<<<<<<< HEAD
=======
=======
FROM python:3.10.0 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app


RUN python -m venv .venv
COPY requirements.txt ./
RUN .venv/bin/pip install -r requirements.txt
FROM python:3.10.0-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY . .
CMD ["/app/.venv/bin/flask", "run", "--host=0.0.0.0", "--port=8080"]
>>>>>>> 9318087e3b7d51b4e5932d3828f104eac2b4f9f5
>>>>>>> c4af594019c9ef580ae7c415f45c042723666157
