FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask flask-cors elasticsearch requests gunicorn

COPY context_lab.py .
COPY app.py .
COPY static/ ./static/

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "1", "app:app"]
