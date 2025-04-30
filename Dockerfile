FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir PyGithub requests

COPY *.py /app/

ENTRYPOINT ["python", "/app/main.py"]