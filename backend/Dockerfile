FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# A lista de dependencias sai do pyproject.toml, e nao repetida aqui: quando as
# duas listas existiam, o pyproject ganhou python-multipart e pypdf e o
# Dockerfile nao. A API subia como container e morria na importacao, sem que
# nenhum teste percebesse - eles rodam num ambiente onde tudo ja esta instalado.
# Copiar so o pyproject nesta etapa mantem o cache: mexer no codigo nao refaz o
# pip install.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
