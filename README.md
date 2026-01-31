## Starting the containers ##
```bash
docker compose up -d
```
OpenAPI docs
http://localhost:8080/docs


## Testing locally ##
```bash
poetry install
poetry shell
fastapi dev msci/main.py
http://127.0.0.1:8000/docs
```

## Building the container ##
if any dependency changes happened
```bash
poetry export --without-hashes --output requirements.txt
poetry export --without-hashes --only dev --output requirements-dev.txt
```
```bash
docker compose build
```

## Tests ##
```bash
poetry run pytest --cov-report=term-missing --cov=msci
```
## Formatting ##
```bash
ruff check
ruff format
```

## Linkting ##
```bash
pylint msci
```
