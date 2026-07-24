FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.4

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./
RUN poetry config virtualenvs.create false && poetry install --only main --no-root && pip install --no-cache-dir -e .

EXPOSE 8002
CMD ["uvicorn", "progression_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
