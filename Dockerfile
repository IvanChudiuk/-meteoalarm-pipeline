FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install -e ".[dev]"

CMD ["python", "-m", "meteoalarm_pipeline.main"]