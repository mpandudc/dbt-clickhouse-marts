FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
    && useradd --create-home --uid 1000 dbt

USER dbt
WORKDIR /app/dbt
ENTRYPOINT ["dbt"]
CMD ["--version"]
