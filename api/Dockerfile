FROM python:3.13.5

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run will set PORT environment variable
ENV PORT=8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}