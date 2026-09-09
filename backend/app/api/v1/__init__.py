"""Agregacao das rotas da versao 1 da API."""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    auth,
    categories,
    dashboard,
    forecast,
    imports,
    investments,
    openfinance,
    planning,
    tax,
    transactions,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(imports.router)
api_router.include_router(dashboard.router)
api_router.include_router(planning.router)
api_router.include_router(forecast.router)
api_router.include_router(investments.router)
api_router.include_router(tax.router)
api_router.include_router(openfinance.router)
