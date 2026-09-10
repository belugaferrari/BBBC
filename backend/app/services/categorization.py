"""Categorizacao inteligente de lancamentos.

O motor e deterministico e explicavel: cada transacao categorizada guarda qual
regra a classificou e com que confianca. O "aprendizado" acontece quando o
Felipe ou a Clarissa corrigem a categoria - a correcao vira (ou reforca) uma
regra de fornecedor, e as proximas transacoes iguais ja entram certas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from app.models.enums import TxDirection

# Ruido tipico de extrato bancario e fatura de cartao.
_NOISE_PATTERNS = [
    r"\bcompra\s+(com\s+)?cart[aã]o\b",
    r"\bcartao\s+de\s+credito\b",
    r"\bdebito\s+automatico\b",
    r"\bpagamento\s+(de\s+)?(fatura|boleto)\b",
    r"\bpix\s+(enviado|recebido|transf)\b",
    r"\bparcela\s+\d+\s*/\s*\d+\b",
    r"\b\d{2}/\d{2}(/\d{2,4})?\b",
    r"\bbr\b",
    r"\*+",
    r"\bltda\b|\bme\b|\beireli\b|\bs\.?a\.?\b",
    r"\b\d{4,}\b",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS))
_NON_WORD_RE = re.compile(r"[^a-z0-9 ]+")
_SPACES_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """minusculo, sem acento, sem ruido de extrato. Base de todo match."""
    lowered = unicodedata.normalize("NFKD", text.lower())
    lowered = "".join(c for c in lowered if not unicodedata.combining(c))
    lowered = _NOISE_RE.sub(" ", lowered)
    lowered = _NON_WORD_RE.sub(" ", lowered)
    return _SPACES_RE.sub(" ", lowered).strip()


def merchant_key(description: str, max_tokens: int = 3) -> str:
    """Extrai a assinatura do fornecedor ('bambu lab', 'drogaria sao paulo').

    Usada tanto para agrupar fornecedores quanto como padrao das regras
    aprendidas a partir de uma correcao manual.
    """
    tokens = [t for t in normalize(description).split() if len(t) > 1]
    return " ".join(tokens[:max_tokens])


@dataclass(frozen=True)
class Rule:
    """Espelho em memoria de `categorization_rules`."""

    id: UUID | None
    pattern: str
    category_id: UUID
    match_type: str = "CONTEM"
    direction: TxDirection | None = None
    account_id: UUID | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    apply_tag_id: UUID | None = None
    ir_deduction_member_id: UUID | None = None
    priority: int = 100
    confidence: Decimal = Decimal("0.5")
    hit_count: int = 0
    is_learned: bool = False


@dataclass(frozen=True)
class TransactionFacts:
    """O minimo que o motor precisa saber de uma transacao."""

    description: str
    amount: Decimal
    direction: TxDirection
    account_id: UUID | None = None


@dataclass(frozen=True)
class Match:
    rule: Rule
    category_id: UUID
    confidence: Decimal
    apply_tag_id: UUID | None = None
    ir_deduction_member_id: UUID | None = None


def _pattern_matches(rule: Rule, normalized: str) -> bool:
    pattern = normalize(rule.pattern) if rule.match_type != "REGEX" else rule.pattern
    match rule.match_type:
        case "EXATO":
            return normalized == pattern
        case "PREFIXO":
            return normalized.startswith(pattern)
        case "REGEX":
            try:
                return re.search(pattern, normalized, re.IGNORECASE) is not None
            except re.error:
                return False
        case _:
            return bool(pattern) and pattern in normalized


def rule_matches(rule: Rule, tx: TransactionFacts) -> bool:
    if rule.direction is not None and rule.direction != tx.direction:
        return False
    if rule.account_id is not None and rule.account_id != tx.account_id:
        return False
    if rule.min_amount is not None and tx.amount < rule.min_amount:
        return False
    if rule.max_amount is not None and tx.amount > rule.max_amount:
        return False
    return _pattern_matches(rule, normalize(tx.description))


def categorize(tx: TransactionFacts, rules: list[Rule]) -> Match | None:
    """Primeira regra que casa, na ordem (prioridade, especificidade, confianca).

    A ESPECIFICIDADE vem antes da confianca de proposito. Com a ordem invertida,
    bastava a regra 'uber' acertar uma corrida para ficar mais confiante que
    'uber eats' - e a partir dali todo delivery viraria transporte, sem ninguem
    perceber. Padrao mais longo descreve o fornecedor com mais precisao, e isso
    nao muda com o uso.
    """
    ordered = sorted(
        rules,
        key=lambda r: (r.priority, -len(r.pattern), -float(r.confidence), -r.hit_count),
    )
    for rule in ordered:
        if rule_matches(rule, tx):
            return Match(
                rule=rule,
                category_id=rule.category_id,
                confidence=rule.confidence,
                apply_tag_id=rule.apply_tag_id,
                ir_deduction_member_id=rule.ir_deduction_member_id,
            )
    return None


# ---------------------------------------------------------------------------
# Aprendizado
# ---------------------------------------------------------------------------
CONFIDENCE_STEP = Decimal("0.15")
CONFIDENCE_PENALTY = Decimal("0.30")
MIN_CONFIDENCE = Decimal("0.100")
MAX_CONFIDENCE = Decimal("0.990")


def _clamp(value: Decimal) -> Decimal:
    return max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, value)).quantize(Decimal("0.001"))


def reinforce(rule: Rule) -> Rule:
    """Usuario confirmou a sugestao: a regra fica mais confiavel."""
    return replace(
        rule,
        confidence=_clamp(rule.confidence + CONFIDENCE_STEP * (1 - rule.confidence)),
        hit_count=rule.hit_count + 1,
    )


def weaken(rule: Rule) -> Rule:
    """Usuario corrigiu uma sugestao desta regra: ela perde confianca."""
    return replace(rule, confidence=_clamp(rule.confidence - CONFIDENCE_PENALTY))


def learn_from_correction(
    tx: TransactionFacts,
    chosen_category_id: UUID,
    existing_rules: list[Rule],
    *,
    ir_deduction_member_id: UUID | None = None,
    apply_tag_id: UUID | None = None,
) -> tuple[Rule, list[Rule]]:
    """Transforma uma recategorizacao manual em conhecimento.

    Devolve (regra a gravar, regras existentes que devem ser enfraquecidas).
    Se ja existe uma regra aprendida para o mesmo fornecedor, ela e apontada
    para a nova categoria em vez de duplicarmos padroes concorrentes.
    """
    pattern = merchant_key(tx.description)
    weakened = [
        weaken(rule)
        for rule in existing_rules
        if rule_matches(rule, tx) and rule.category_id != chosen_category_id
    ]

    for rule in existing_rules:
        if rule.is_learned and normalize(rule.pattern) == pattern:
            updated = replace(
                rule,
                category_id=chosen_category_id,
                ir_deduction_member_id=ir_deduction_member_id or rule.ir_deduction_member_id,
                apply_tag_id=apply_tag_id or rule.apply_tag_id,
                confidence=_clamp(rule.confidence + CONFIDENCE_STEP),
                hit_count=rule.hit_count + 1,
            )
            return updated, weakened

    # Regra aprendida nasce com prioridade melhor que as genericas do catalogo.
    new_rule = Rule(
        id=None,
        pattern=pattern,
        category_id=chosen_category_id,
        match_type="CONTEM",
        direction=tx.direction,
        apply_tag_id=apply_tag_id,
        ir_deduction_member_id=ir_deduction_member_id,
        priority=50,
        confidence=Decimal("0.700"),
        hit_count=1,
        is_learned=True,
    )
    return new_rule, weakened
