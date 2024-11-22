FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y \
            python3-pip \
            cron \
            poppler-utils

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]