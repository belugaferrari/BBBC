FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
      "fastapi>=0.115" "uvicorn[standard]>=0.32" "sqlalchemy>=2.0.36" \
      "psycopg[binary]>=3.2" "pydantic>=2.9" "pydantic-settings>=2.6" \
      "python-jose[cryptography]>=3.3" "bcrypt>=4.2" "httpx>=0.27" \
      "python-dateutil>=2.9"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
