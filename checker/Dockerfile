FROM python:3.12-slim

WORKDIR /app
COPY checker/pyproject.toml /app/pyproject.toml
COPY checker/src /app/src
RUN pip install --no-cache-dir .
COPY demo-target /demo-target

ENV DEMO_ROOT=/demo-target
ENV BREACHMIRROR_ROOT=/srv
ENV CASE_DIR=/data/cases
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "breachmirror.api:app", "--host", "0.0.0.0", "--port", "8000"]
