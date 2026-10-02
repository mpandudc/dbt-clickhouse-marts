.PHONY: config up down clean image load build docs docs-serve check verify

START ?= 2026-01-01
DAYS ?= 45
RUN = docker compose run --rm

config:
	docker compose config --quiet

up:
	docker compose up -d --wait clickhouse

down:
	docker compose down

clean:
	docker compose down --volumes --remove-orphans

image:
	docker compose --profile tools build dbt

load: up
	$(RUN) --entrypoint python dbt /app/scripts/load_raw.py --start $(START) --days $(DAYS)

build: up
	$(RUN) dbt build

docs: up
	$(RUN) dbt docs generate

# Web UI on http://localhost:18090 (lineage + catalog); run after `make build`.
docs-serve: up
	docker compose --profile docs up -d docs

check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_project.py

verify:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_runtime.py
