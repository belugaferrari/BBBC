# Importando extratos do banco

Alternativa ao Open Finance: você exporta o extrato pelo site do banco e envia
pelo app. Funciona hoje, sem contratar nada.

## Formatos aceitos

| Formato | Qualidade da leitura | Quando usar |
|---|---|---|
| **OFX** (`.ofx`, `.ofc`, `.qfx`) | **Exata** | Sempre que o banco oferecer. Cada lançamento vem com identificador próprio (FITID), então a deduplicação é perfeita. |
| **CSV** (`.csv`, `.txt`) | Muito boa | Segunda opção. O leitor identifica as colunas pelo nome e, se não achar cabeçalho, deduz pelo conteúdo. |
| **PDF** | Aproximada | Último recurso. Funciona, mas confira antes de confirmar. |

Quase todo banco brasileiro exporta OFX — costuma aparecer como "Exportar para
o gerenciador financeiro", "OFX" ou "Money/Quicken". Vale procurar: é a
diferença entre importação exata e importação por aproximação.

**Sobre PDF, sem rodeios:** PDF não é formato de dados, é formato de impressão.
O leitor reconhece linhas no padrão `data … descrição … valor`, que cobre a
maioria dos extratos, mas cada banco diagrama do seu jeito e muda o leiaute sem
avisar. PDF escaneado (imagem) não funciona de jeito nenhum — não há texto para
extrair. Por isso lançamentos vindos de PDF ficam marcados com origem própria
no banco de dados: são os que merecem um olhar antes de virarem verdade.

## Como funciona

São dois passos, de propósito.

**1. Envio.** O arquivo é lido e devolvido como uma proposta. **Nada é gravado
aqui.** Você vê cada lançamento, com a categoria que o sistema sugeriu.

**2. Conferência.** Linhas que já existem vêm desmarcadas, com o motivo escrito
("já importado antes", "já importado em outro formato", "você já lançou este
valor à mão"). Você marca e desmarca o que quiser e confirma.

Gravar direto seria mais rápido, e seria a forma mais fácil de sujar a base.
Sujeira em base financeira custa horas de conferência depois.

## O que impede lançamento duplicado

Três camadas, da mais exata para a mais tolerante:

1. **Identificador do banco.** Se o arquivo traz FITID (OFX), ele é soberano.
2. **Impressão digital.** Data + valor + direção + descrição normalizada,
   com índice único no banco por conta. Mesmo duas confirmações simultâneas não
   duplicam.
3. **Equivalência.** Mesmo valor, mesma direção, até 3 dias de diferença. É o
   que pega a compra que você digitou à mão antes de o banco publicar, e o
   mesmo período importado em dois formatos diferentes.

Isso está coberto por teste: importar o mesmo extrato duas vezes, e depois o
mesmo período em CSV e OFX, continua com cinco lançamentos.

## Se o seu banco não for reconhecido

O leitor de CSV entende as variações comuns (`Data`/`Date`, `Histórico`/
`Descrição`/`Lançamento`, `Valor` ou colunas separadas de `Débito` e `Crédito`,
separador `;` ou `,`, valores `1.234,56` ou `1,234.56`). Se ainda assim falhar,
a mensagem de erro diz o que não foi reconhecido — me mande o cabeçalho do
arquivo (sem os valores) e eu acrescento o padrão.

## Arquivos de exemplo

`backend/db/samples/` tem o mesmo extrato nos três formatos, para você testar o
fluxo antes de mexer com dados reais.
