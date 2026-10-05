"""Ler "PARCELA 02/10" na descricao, sem confundir com uma data.

"Contas parceladas devem aparecer em todos os meses em que ainda estao vigentes
as parcelas (nao apenas no mes de contratacao)."

Cada fatura cobra uma parcela, e e assim que elas se espalham pelos meses: a
fatura de outubro traz a 02/10, a de novembro traz a 03/10. Importando fatura a
fatura, o sistema ja acerta sozinho - o `paid_on` de cada linha e o vencimento da
fatura que a trouxe.

O que a leitura da descricao acrescenta sao duas coisas que nenhuma linha
sozinha conta:

  * QUANTO FOI A COMPRA. "R$ 300" numa fatura e um pedaco de uma compra de
    R$ 3.000 feita ha oito meses. Sem o "02/10", a tela nao tem como dizer isso.
  * O QUE AINDA VEM. Sabendo que esta e a 2 de 10, da para mostrar as outras
    oito nos meses em que vao cair, antes de a fatura chegar.

O RISCO, e por que o leitor e desconfiado: "02/10" tambem e uma data. "IFOOD
02/10" quase certamente e um pedido do dia 2 de outubro, e nao a segunda de dez
parcelas. Entao o numero solto so vale quando o total NAO PODE ser um mes - de
13 em diante. Nos outros casos, exige-se a palavra ("PARCELA", "PARC") ou o
"de" por extenso. Errar para menos aqui custa uma informacao a mais na tela;
errar para mais inventa uma compra de dez vezes o valor.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

# Mais que isso nao e parcelamento de cartao, e erro de leitura.
_MAXIMO_DE_PARCELAS = 72

_SEPARADOR = r"(?:/|\s+de\s+|\s*-\s*)"

# Com marca explicita: "PARCELA 2/10", "PARC 02 DE 10", "P 3/12".
_COM_MARCA = re.compile(
    rf"\bparc(?:ela)?\.?\s*(\d{{1,2}})\s*{_SEPARADOR}\s*(\d{{1,2}})\b",
    re.IGNORECASE,
)
# Entre parenteses, que e como o proprio sistema escreve: "(2/10)".
_ENTRE_PARENTESES = re.compile(r"\((\d{1,2})\s*/\s*(\d{1,2})\)")
# Por extenso, no fim: "LOJA X 2 DE 10".
_POR_EXTENSO = re.compile(r"\b(\d{1,2})\s+de\s+(\d{1,2})\s*$", re.IGNORECASE)
# Solto, no fim da descricao - e so quando o total nao pode ser um mes.
_SOLTO_NO_FIM = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*$")


@dataclass(frozen=True)
class Parcela:
    numero: int
    total: int

    @property
    def e_a_ultima(self) -> bool:
        return self.numero >= self.total

    @property
    def quantas_faltam(self) -> int:
        return max(self.total - self.numero, 0)

    def valor_da_compra(self, valor_da_parcela: Decimal) -> Decimal:
        """O que a compra custou, somadas todas as parcelas.

        E uma estimativa honesta, e nao um dado: parcelamento com juros tem
        parcelas diferentes entre si, e a primeira as vezes vem quebrada. Serve
        para a tela dizer "parcela 2 de 10 de uma compra de R$ 3.000", que e
        incomparavelmente mais util do que nao dizer nada - e para nada mais.
        """
        return (valor_da_parcela * self.total).quantize(Decimal("0.01"))


def _sem_acento(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in plano if not unicodedata.combining(c))


def ler_parcela(descricao: str) -> Parcela | None:
    """A parcela escrita na descricao, se houver uma de que se possa ter certeza."""
    texto = _sem_acento(descricao or "").strip()
    if not texto:
        return None

    for padrao in (_COM_MARCA, _ENTRE_PARENTESES, _POR_EXTENSO):
        achado = padrao.search(texto)
        if achado:
            return _validar(achado.group(1), achado.group(2))

    achado = _SOLTO_NO_FIM.search(texto)
    if achado and int(achado.group(2)) > 12:
        # 13 em diante nao e mes nenhum, entao nao e data
        return _validar(achado.group(1), achado.group(2))
    return None


def _validar(numero: str, total: str) -> Parcela | None:
    n, t = int(numero), int(total)
    if t < 2 or n < 1 or n > t or t > _MAXIMO_DE_PARCELAS:
        return None
    return Parcela(numero=n, total=t)


_MARCAS = (_COM_MARCA, _ENTRE_PARENTESES, _POR_EXTENSO, _SOLTO_NO_FIM)


def raiz_da_descricao(descricao: str) -> str:
    """A descricao sem a marca de parcela, para as parcelas de uma mesma compra
    se reconhecerem.

    "MAGAZINE PARCELA 02/10" e "MAGAZINE PARCELA 03/10" sao a mesma compra vista
    em duas faturas. E so por aqui que a parcela que chega consegue encontrar a
    previsao que ela vem ocupar - sem isso, a previsao ficaria no lugar e o mes
    contaria a parcela duas vezes.
    """
    texto = _sem_acento(descricao or "").lower()
    for padrao in _MARCAS:
        texto = padrao.sub(" ", texto)
    return " ".join(texto.split())


def numerar(descricao: str, parcela: Parcela) -> str:
    """A descricao de uma parcela futura, escrita do jeito que o leitor entende.

    Vai aparecer na tela ("MAGAZINE (3/10)") e e por ela que a parcela de
    verdade, quando a fatura chegar, reconhece esta previsao.
    """
    return f"{raiz_da_descricao(descricao).upper().strip()} ({parcela.numero}/{parcela.total})"
