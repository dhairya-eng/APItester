FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Single worker per container — we scale by running MORE containers,
# not more workers per container. This is the horizontal-scaling mindset.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]