"""Leitor de planilha do Excel (.xlsx / .xlsm).

O banco dele oferece a fatura do cartao em planilha, e planilha nao e CSV: e um
zip com varios XML dentro. Este modulo abre esse zip, transforma a primeira aba
numa grade de texto e entrega para o MESMO leitor que ja entende extrato em CSV
- a inteligencia de achar as colunas (data, descricao, valor, debito/credito)
mora la e nao precisa existir duas vezes.

POR QUE SEM BIBLIOTECA. Daria para usar openpyxl, que e boa. Mas cada biblioteca
a mais e uma coisa a mais para faltar na maquina dele depois de uma atualizacao -
ja aconteceu, e o sintoma e sempre um pedaco do sistema que simplesmente nao
funciona, sem dizer por que. O que um extrato em planilha usa do formato e pouco:
celula de texto, celula de numero, celula de data. Isso cabe em `zipfile` e
`xml.etree`, que vem com o Python.

AS DUAS ARMADILHAS DO FORMATO, que e onde um leitor ingenuo erra:

  1. DATA E NUMERO. O Excel nao guarda "05/09/2026": guarda 46270, e diz em
     outro arquivo (`styles.xml`) que aquela celula e para ser mostrada como
     data. Sem ler o estilo, toda data vira um numero grande e o extrato inteiro
     se perde.
  2. CELULA VAZIA NAO OCUPA LUGAR. O XML pula a celula em branco em vez de
     escreve-la vazia - cada celula traz o proprio endereco ("C7"). Ler em
     sequencia desalinharia as colunas a partir do primeiro buraco, e a coluna
     de valor passaria a ser lida como descricao.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date, timedelta
from io import BytesIO
from xml.etree import ElementTree

from app.services.importers.base import ParsedStatement, StatementParseError
from app.services.importers.csv_statement import montar_extrato

# O conteudo descompactado de uma planilha de extrato cabe de sobra aqui. O teto
# existe porque zip pequeno pode descompactar em gigabytes, e o limite de tamanho
# do upload so ve o arquivo compactado.
_MAX_DESCOMPACTADO = 80 * 1024 * 1024
_MAX_LINHAS = 20_000

# Formatos de data embutidos no Excel (os ids sao fixos pela especificacao).
_FORMATOS_DE_DATA = frozenset({14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47})

# Numero de serie 0 e 30/12/1899 - o "bug do ano 1900" do Lotus 1-2-3, que o
# Excel copiou de proposito para ser compativel e nunca corrigiu.
_EPOCA_1900 = date(1899, 12, 30)
_EPOCA_1904 = date(1904, 1, 1)

_COLUNA_RE = re.compile(r"^([A-Z]+)")


def _nome(tag: str) -> str:
    """Nome da etiqueta sem o espaco de nomes: `{...}row` -> `row`."""
    return tag.rpartition("}")[2]


def _indice_da_coluna(referencia: str) -> int | None:
    """`C7` -> 2. Devolve None quando a celula nao diz onde esta."""
    casou = _COLUNA_RE.match(referencia or "")
    if not casou:
        return None
    indice = 0
    for letra in casou.group(1):
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return indice - 1


def _texto_de(elemento) -> str:  # noqa: ANN001 - Element
    """Todo o texto de dentro, incluindo o de texto formatado em pedacos.

    Uma celula com parte do texto em negrito vira varios `<r><t>` em vez de um
    `<t>` so. Pegar apenas o primeiro perderia metade da descricao.
    """
    return "".join(no.text or "" for no in elemento.iter() if _nome(no.tag) == "t")


def _abrir(content: bytes) -> zipfile.ZipFile:
    try:
        arquivo = zipfile.ZipFile(BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise StatementParseError(
            "o arquivo nao abriu como planilha. Se ele for .xls (formato antigo), "
            "abra no Excel e salve como .xlsx - ou exporte em CSV."
        ) from exc

    total = sum(item.file_size for item in arquivo.infolist())
    if total > _MAX_DESCOMPACTADO:
        raise StatementParseError("planilha grande demais para ser lida aqui")
    return arquivo


def _textos_compartilhados(arquivo: zipfile.ZipFile) -> list[str]:
    """A tabela de textos da planilha.

    O Excel nao repete texto: escreve cada um uma vez aqui e, nas celulas, so o
    numero da posicao.
    """
    if "xl/sharedStrings.xml" not in arquivo.namelist():
        return []
    raiz = ElementTree.fromstring(arquivo.read("xl/sharedStrings.xml"))
    return [_texto_de(item) for item in raiz if _nome(item.tag) == "si"]


def _estilos_de_data(arquivo: zipfile.ZipFile) -> set[int]:
    """Quais estilos de celula significam "isto e uma data".

    Sao duas listas: os formatos embutidos (ids fixos) e os que a propria
    planilha inventou, que vem com o desenho escrito ("dd/mm/yyyy").
    """
    if "xl/styles.xml" not in arquivo.namelist():
        return set()
    raiz = ElementTree.fromstring(arquivo.read("xl/styles.xml"))

    personalizados: set[int] = set()
    for grupo in raiz:
        if _nome(grupo.tag) != "numFmts":
            continue
        for formato in grupo:
            desenho = (formato.get("formatCode") or "").lower()
            # o que esta entre aspas e texto literal, e nao parte do desenho
            sem_literais = re.sub(r'"[^"]*"', "", desenho)
            if any(marca in sem_literais for marca in ("yy", "dd", "mm/", "/m", "d/m")):
                personalizados.add(int(formato.get("numFmtId", -1)))

    datas: set[int] = set()
    for grupo in raiz:
        if _nome(grupo.tag) != "cellXfs":
            continue
        for posicao, estilo in enumerate(grupo):
            try:
                formato = int(estilo.get("numFmtId", 0))
            except ValueError:
                continue
            if formato in _FORMATOS_DE_DATA or formato in personalizados:
                datas.add(posicao)
    return datas


def _primeira_aba(arquivo: zipfile.ZipFile) -> str:
    """O caminho da primeira aba, seguindo o que o proprio arquivo declara.

    Ordem alfabetica nao serve: `sheet10.xml` viria antes de `sheet2.xml`, e a
    primeira aba da planilha pode nem se chamar sheet1.
    """
    try:
        livro = ElementTree.fromstring(arquivo.read("xl/workbook.xml"))
        relacoes = ElementTree.fromstring(arquivo.read("xl/_rels/workbook.xml.rels"))
    except KeyError as exc:
        raise StatementParseError("planilha sem a estrutura esperada") from exc

    destino_por_id = {
        item.get("Id"): item.get("Target", "")
        for item in relacoes
        if _nome(item.tag) == "Relationship"
    }

    for grupo in livro:
        if _nome(grupo.tag) != "sheets":
            continue
        for aba in grupo:
            for chave, valor in aba.attrib.items():
                if _nome(chave) != "id":
                    continue
                destino = destino_por_id.get(valor, "")
                if destino:
                    destino = destino.lstrip("/")
                    return destino if destino.startswith("xl/") else f"xl/{destino}"

    candidatos = [n for n in arquivo.namelist() if n.startswith("xl/worksheets/sheet")]
    if not candidatos:
        raise StatementParseError("planilha sem nenhuma aba")
    return sorted(candidatos)[0]


def _data1904(arquivo: zipfile.ZipFile) -> bool:
    """O Excel do Mac antigo contava os dias a partir de 1904."""
    try:
        livro = ElementTree.fromstring(arquivo.read("xl/workbook.xml"))
    except KeyError:
        return False
    for grupo in livro:
        if _nome(grupo.tag) == "workbookPr":
            return (grupo.get("date1904") or "").lower() in {"1", "true"}
    return False


def _numero_para_data(valor: str, epoca: date) -> str | None:
    try:
        serial = float(valor)
    except ValueError:
        return None
    # datas de extrato ficam entre 1990 e 2100; fora disso e numero mesmo
    if not 30_000 < serial < 80_000:
        return None
    return (epoca + timedelta(days=int(serial))).strftime("%d/%m/%Y")


def celulas(content: bytes) -> list[list[str]]:
    """A primeira aba como grade de texto, com as colunas no lugar."""
    arquivo = _abrir(content)
    textos = _textos_compartilhados(arquivo)
    estilos_de_data = _estilos_de_data(arquivo)
    epoca = _EPOCA_1904 if _data1904(arquivo) else _EPOCA_1900

    raiz = ElementTree.fromstring(arquivo.read(_primeira_aba(arquivo)))
    linhas: list[list[str]] = []

    for bloco in raiz.iter():
        if _nome(bloco.tag) != "row":
            continue
        linha: list[str] = []
        for celula in bloco:
            if _nome(celula.tag) != "c":
                continue
            # cada celula diz o proprio endereco: e assim que a coluna vazia
            # continua ocupando lugar na grade
            destino = _indice_da_coluna(celula.get("r", ""))
            if destino is None:
                destino = len(linha)
            while len(linha) < destino:
                linha.append("")

            tipo = celula.get("t")
            bruto = ""
            for dentro in celula:
                etiqueta = _nome(dentro.tag)
                if etiqueta == "v":
                    bruto = dentro.text or ""
                elif etiqueta == "is":
                    bruto, tipo = _texto_de(dentro), "inlineStr"

            if tipo == "s":
                try:
                    valor = textos[int(bruto)]
                except (ValueError, IndexError):
                    valor = ""
            elif tipo in {"inlineStr", "str"}:
                valor = bruto
            elif tipo == "b":
                valor = "VERDADEIRO" if bruto == "1" else "FALSO"
            else:
                valor = bruto
                try:
                    estilo = int(celula.get("s", -1))
                except ValueError:
                    estilo = -1
                if estilo in estilos_de_data:
                    como_data = _numero_para_data(bruto, epoca)
                    if como_data:
                        valor = como_data
                elif valor.endswith(".0"):
                    # 1234.0 e um inteiro que o Excel escreveu com casa decimal
                    valor = valor[:-2]

            linha.append(valor.strip())

        if any(celula for celula in linha):
            linhas.append(linha)
        if len(linhas) >= _MAX_LINHAS:
            break

    return linhas


def parse(content: bytes) -> ParsedStatement:
    linhas = celulas(content)
    if not linhas:
        raise StatementParseError("a planilha nao tem nenhuma linha preenchida")
    return montar_extrato(linhas, file_format="XLSX")
