FROM python:3.12-slim

# Install system deps for pdfplumber, psycopg2, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /app/candidate_data/resumes/base /app/candidate_data/resumes/tailored

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
