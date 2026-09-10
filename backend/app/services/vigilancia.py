"""O que o sistema vigia sozinho: extratos que faltam, contas a vencer e
pontos prestes a expirar.

Modulo puro: recebe os fatos ja lidos do banco e devolve os avisos. Quem grava
e quem envia sao outros - assim da para testar cada aviso sem banco nem rede.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.services.money import brl, format_brl


@dataclass(frozen=True)
class Aviso:
    kind: str
    severity: str            # INFO | ATENCAO | CRITICO
    title: str
    body: str
    # chave estavel: e o que impede o mesmo aviso de nascer de novo todo dia
    dedupe_key: str
    due_on: date | None = None
    payload: dict | None = None


# ---------------------------------------------------------------------------
# 3. Recebimento de extrato mensal
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ContaEsperada:
    account_id: str
    name: str
    institution: str | None
    expected_day: int | None
    received_at: date | None      # data da importacao confirmada do mes


def checklist_extratos(
    contas: list[ContaEsperada], month: date, today: date | None = None
) -> dict:
    """Quais bancos ja mandaram o extrato do mes e quais nao.

    O extrato recebido nao e um registro novo: e a propria importacao
    confirmada. Guardar o mesmo fato duas vezes so criaria a chance de os dois
    discordarem.
    """
    today = today or date.today()
    referencia = month.replace(day=1)

    recebidas, pendentes, atrasadas = [], [], []
    for conta in contas:
        item = {
            "account_id": conta.account_id,
            "name": conta.name,
            "institution": conta.institution,
            "expected_day": conta.expected_day,
            "received_at": conta.received_at.isoformat() if conta.received_at else None,
        }
        if conta.received_at:
            recebidas.append(item)
            continue

        # so e atraso depois do dia em que o extrato costuma ficar pronto
        vencido = (
            conta.expected_day is not None
            and today >= referencia.replace(
                day=min(conta.expected_day, 28)
            )
        )
        item["days_late"] = (
            (today - referencia.replace(day=min(conta.expected_day, 28))).days
            if vencido
            else None
        )
        (atrasadas if vencido else pendentes).append(item)

    return {
        "month": referencia.isoformat(),
        "expected": len(contas),
        "received": len(recebidas),
        "missing": len(pendentes) + len(atrasadas),
        "complete": not pendentes and not atrasadas,
        "received_list": recebidas,
        "pending_list": pendentes,
        "late_list": atrasadas,
    }


def avisos_de_extrato(checklist: dict) -> list[Aviso]:
    avisos = []
    for conta in checklist["late_list"]:
        avisos.append(
            Aviso(
                kind="EXTRATO_ATRASADO",
                severity="ATENCAO",
                title=f"Extrato de {conta['name']} ainda nao chegou",
                body=(
                    f"O extrato costuma sair no dia {conta['expected_day']} e ja "
                    f"faz {conta['days_late']} dias. Sem ele, o mes fica incompleto."
                ),
                dedupe_key=f"extrato:{conta['account_id']}:{checklist['month']}",
                payload={"account_id": conta["account_id"]},
            )
        )
    return avisos


# ---------------------------------------------------------------------------
# 4. Vencimento de contas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ContaAVencer:
    id: str
    description: str
    amount: Decimal
    due_on: date
    remind_days_before: int = 3
    account_name: str | None = None


def avisos_de_vencimento(
    contas: list[ContaAVencer], today: date | None = None
) -> list[Aviso]:
    """Um aviso por conta, dentro da janela de antecedencia de cada uma.

    A antecedencia e por conta e nao global de proposito: a fatura do cartao
    precisa de mais dias do que a conta de luz, porque o dinheiro para paga-la
    costuma vir de outro lugar.
    """
    today = today or date.today()
    avisos: list[Aviso] = []

    for conta in contas:
        dias = (conta.due_on - today).days
        if dias > conta.remind_days_before:
            continue

        if dias < 0:
            severity, quando = "CRITICO", f"venceu ha {abs(dias)} dia(s)"
        elif dias == 0:
            severity, quando = "CRITICO", "vence hoje"
        elif dias == 1:
            severity, quando = "ATENCAO", "vence amanha"
        else:
            severity, quando = "ATENCAO", f"vence em {dias} dias"

        avisos.append(
            Aviso(
                kind="CONTA_A_VENCER",
                severity=severity,
                title=f"{conta.description} {quando}",
                body=(
                    f"{format_brl(conta.amount)} com vencimento em "
                    f"{conta.due_on.strftime('%d/%m')}"
                    + (f" · {conta.account_name}" if conta.account_name else "")
                ),
                dedupe_key=f"vencimento:{conta.id}:{conta.due_on.isoformat()}",
                due_on=conta.due_on,
                payload={"amount": str(brl(conta.amount))},
            )
        )
    return avisos


# ---------------------------------------------------------------------------
# 6. Pontos a expirar
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PontosAExpirar:
    program_id: str
    name: str
    points: Decimal
    expires_on: date
    value_brl: Decimal | None = None


def avisos_de_pontos(
    programas: list[PontosAExpirar], today: date | None = None, dias_antes: int = 60
) -> list[Aviso]:
    """Ponto que expira sem ser usado e dinheiro jogado fora. O aviso sai com
    folga porque resgate de milha nao se faz na vespera."""
    today = today or date.today()
    avisos: list[Aviso] = []

    for programa in programas:
        dias = (programa.expires_on - today).days
        if dias > dias_antes or programa.points <= 0:
            continue

        valor = (
            f" (cerca de {format_brl(programa.value_brl)})" if programa.value_brl else ""
        )
        avisos.append(
            Aviso(
                kind="PONTOS_A_EXPIRAR",
                severity="CRITICO" if dias <= 15 else "ATENCAO",
                title=(
                    f"{programa.points:,.0f} pontos {programa.name} expiram em "
                    f"{dias} dias"
                ).replace(",", "."),
                body=(
                    f"Vencem em {programa.expires_on.strftime('%d/%m/%Y')}{valor}. "
                    "Depois disso viram pó."
                ),
                dedupe_key=(
                    f"pontos:{programa.program_id}:{programa.expires_on.isoformat()}"
                ),
                due_on=programa.expires_on,
            )
        )
    return avisos


def proximo_vencimento(dia_do_mes: int, hoje: date | None = None) -> date:
    """Proxima ocorrencia de um dia fixo do mes, sem estourar em mes curto."""
    hoje = hoje or date.today()
    dia = min(dia_do_mes, 28)
    candidato = hoje.replace(day=dia)
    if candidato < hoje:
        proximo = hoje.replace(day=1) + timedelta(days=32)
        candidato = proximo.replace(day=dia)
    return candidato
