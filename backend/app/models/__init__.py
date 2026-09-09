"""Modelos ORM. Importar deste pacote garante o registro no metadata do SQLAlchemy."""

from app.models.base import Base
from app.models.family import Account, BankConnection, Family, Institution, Member
from app.models.imports import StatementImport
from app.models.investments import (
    Asset,
    BenchmarkSeries,
    InvestmentTransaction,
    Position,
    PositionSnapshot,
)
from app.models.ledger import (
    RecurringTransaction,
    Transaction,
    TransactionSplit,
    TransactionTag,
)
from app.models.ops import Alert, SyncLog, WebhookEvent
from app.models.planning import BudgetCap, Goal, GoalContribution
from app.models.tax import IRAssessment, IRIncomeStatement, TaxBracket, TaxParameter, TaxYear
from app.models.taxonomy import CategorizationRule, Category, Merchant, Tag

__all__ = [
    "Account", "Alert", "Asset", "BankConnection", "Base", "BenchmarkSeries", "BudgetCap",
    "CategorizationRule", "Category", "Family", "Goal", "GoalContribution", "IRAssessment",
    "IRIncomeStatement", "Institution", "InvestmentTransaction", "Member", "Merchant",
    "Position", "PositionSnapshot", "RecurringTransaction", "StatementImport", "SyncLog",
    "Tag", "TaxBracket",
    "TaxParameter", "TaxYear", "Transaction", "TransactionSplit", "TransactionTag",
    "WebhookEvent",
]
