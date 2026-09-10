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
from app.models.notifications import NotificationDelivery, NotificationTarget
from app.models.ops import Alert, SyncLog, WebhookEvent
from app.models.patrimonio import Holding, HoldingValuation
from app.models.planning import BudgetCap, Goal, GoalContribution
from app.models.points import CardProgram, PointMovement
from app.models.tax import IRAssessment, IRIncomeStatement, TaxBracket, TaxParameter, TaxYear
from app.models.taxonomy import CategorizationRule, Category, Merchant, Tag

__all__ = [
    "Account", "Alert", "Asset", "BankConnection", "Base", "BenchmarkSeries", "BudgetCap",
    "CardProgram",
    "CategorizationRule", "Category", "Family", "Goal", "GoalContribution", "IRAssessment",
    "Holding", "HoldingValuation", "IRIncomeStatement", "Institution",
    "InvestmentTransaction", "Member", "Merchant", "NotificationDelivery",
    "NotificationTarget", "PointMovement",
    "Position", "PositionSnapshot", "RecurringTransaction", "StatementImport", "SyncLog",
    "Tag", "TaxBracket",
    "TaxParameter", "TaxYear", "Transaction", "TransactionSplit", "TransactionTag",
    "WebhookEvent",
]
