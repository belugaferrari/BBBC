"""O que o servidor NAO manda para o aplicativo.

Isto nao e formatacao de tela. Com o aplicativo guardando uma copia dos dados
no celular para funcionar offline, o que o servidor envia e o que fica gravado
no aparelho - e o que fica gravado e o que vaza se o celular for perdido.
Esconder so na hora de desenhar deixaria o nome completo e o numero da conta
em texto puro no armazenamento local, que e exatamente o risco a evitar.

Por isso o corte e aqui: o valor sensivel nao sai do servidor. Ele continua no
banco de dados, em casa, para o que de fato precisa dele - a declaracao de
imposto de renda precisa do nome completo do dependente, e a conciliacao
precisa do identificador da conta no provedor.
"""

from __future__ import annotations

import re

# "de", "da", "do" nao viram inicial: "Maria da Silva" e "Maria S.", nao
# "Maria D. S.".
_PARTICULAS = {"de", "da", "do", "das", "dos", "e", "d"}

# Agencia tem 4 digitos, conta corrente de 5 a 8, cartao 16. Tres digitos ou
# menos sobrevivem: "Conta 2" e "Carteira 10" sao nomes legitimos, e apaga-los
# tornaria a lista de contas indistinguivel.
_SEQUENCIA_DE_DIGITOS = re.compile(r"\d[\d.\-/\s]{2,}\d|\d{4,}")

MASCARA = "••••"  # ••••


def nome_curto(nome: str | None) -> str:
    """'Cecilia Ferrari' -> 'Cecilia F.'

    O primeiro nome fica inteiro: e por ele que a familia se reconhece na tela.
    O sobrenome vira inicial, que e o que identifica a pessoa para quem nao
    deveria estar olhando.
    """
    if not nome:
        return ""
    partes = [p for p in nome.strip().split() if p]
    if not partes:
        return ""
    primeiro, resto = partes[0], partes[1:]
    iniciais = [
        f"{p[0].upper()}."
        for p in resto
        if p.lower().strip(".") not in _PARTICULAS and p
    ]
    return " ".join([primeiro, *iniciais])


def sigla_instituicao(nome: str | None) -> str:
    """'Banco do Brasil' -> 'BB'. 'Nubank' -> 'NU'.

    Suficiente para a familia saber de qual banco veio o extrato, sem anunciar
    onde o dinheiro esta guardado para quem pegar o aparelho.
    """
    if not nome:
        return ""
    palavras = [
        p for p in re.split(r"[\s/_-]+", nome.strip())
        if p and p.lower().strip(".") not in _PARTICULAS
    ]
    if not palavras:
        return ""
    if len(palavras) == 1:
        return palavras[0][:2].upper()
    return "".join(p[0] for p in palavras[:3]).upper()


def sem_digitos_sensiveis(texto: str | None) -> str:
    """Esconde agencia, conta e cartao dentro de um texto livre.

    Vale para o que o usuario mesmo digitou (o nome da conta) e para o que veio
    de fora (o nome do arquivo do extrato, que costuma trazer banco e conta no
    proprio nome).
    """
    if not texto:
        return ""
    return _SEQUENCIA_DE_DIGITOS.sub(MASCARA, texto)
