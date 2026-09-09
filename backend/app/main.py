"""Ponto de entrada da API do BBBC."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings

settings.assert_production_ready()

app = FastAPI(
    title="BBBC - Gestao Financeira Familiar",
    version="0.1.0",
    description=(
        "API do sistema financeiro da familia. Modulos: dashboard, gastos, "
        "previsoes, investimentos e imposto de renda."
    ),
)

# O app mobile consome a API por HTTPS; a lista fica restrita em producao.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}
