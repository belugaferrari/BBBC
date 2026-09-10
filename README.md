# BBBC — Gestão financeira da família

Sistema de finanças familiares para o Felipe e a Clarissa: um app mobile sobre
uma API em Python, com fluxo de caixa, categorização automática, previsões,
consolidação de investimentos e apuração de Imposto de Renda.

## Stack

| Camada | Escolha |
|---|---|
| App | React Native (Expo) + TypeScript |
| API | FastAPI (Python 3.11+), SQLAlchemy 2.0 |
| Banco | PostgreSQL 15+ (`ltree`, `pg_trgm`, `unaccent`) |
| Open Finance | Contrato único com implementações Pluggy e Belvo; modo manual por padrão |
| Importação | Extrato do banco em OFX, CSV ou PDF, com conferência antes de gravar |

Paleta do app: preto, branco e vermelho. O vermelho é reservado para o que pede
atenção (saída de dinheiro, teto estourado, imposto a pagar) — usar vermelho em
tudo tiraria o poder do alerta.

## Rodando

```bash
cp backend/.env.example backend/.env      # ajuste SECRET_KEY e DATABASE_URL
docker compose up --build                 # sobe Postgres + API em :8000

# ou, sem Docker:
cd backend && pip install -e ".[dev]"
python -m app.cli migrate
python -m app.cli seed-family --name "Familia BBBC" \
  --titular "Felipe"   --titular-email felipe@exemplo.com   --titular-password ... \
  --conjuge "Clarissa" --conjuge-email clarissa@exemplo.com --conjuge-password ... \
  --dependente "Filha 1" --dependente "Filha 2"
uvicorn app.main:app --reload

cd ../mobile && npm install && npm start   # ajuste extra.apiBaseUrl no app.json
```

Documentação interativa da API em `http://localhost:8000/docs`.

**Primeira vez, sem familiaridade com terminal?**
[`COMECE-AQUI.md`](COMECE-AQUI.md) sobe tudo com dois cliques.
**Quer entender cada comando?** [`docs/testando-o-sistema.md`](docs/testando-o-sistema.md)
leva do zero até ver o IR calculado, com extratos de exemplo.

## Testes

```bash
cd backend
python -m pytest -q                        # 73 testes de regra de negócio, sem banco

createdb bbbc_test
BBBC_TEST_DATABASE_URL=postgresql+psycopg://bbbc:bbbc@localhost/bbbc_test \
  python -m pytest -q                      # 103 testes, com a integração
```

A suíte rápida cobre o motor de IR, o simulador de metas, a categorização, a
geometria do Sankey e a leitura dos três formatos de extrato. A de integração
sobe a API de verdade contra um Postgres e verifica, além do fluxo feliz, que o
token de uma família não alcança nada de outra e que reimportar o mesmo extrato
— inclusive em outro formato — não duplica lançamento.

## Estrutura

```
backend/
  app/
    api/v1/         endpoints (auth, contas, categorias, gastos, dashboard,
                    previsões, investimentos, IR, open finance)
    services/       regras de negócio puras e testáveis
      tax.py          motor de IR (tabela progressiva, deduções, carnê-leão)
      projection.py   metas, tetos e simulação de aportes
      forecast.py     evolutivo dos próximos meses (fixo, esperado, estimado)
      categorization.py  motor de regras + aprendizado de fornecedores
      import_service.py  importação de extrato: prever, conferir, gravar
      importers/      leitores de OFX, CSV e PDF
      investments.py  consolidação, TWR e comparativo CDI/IPCA
      sankey.py       montagem do gráfico em cascata
    models/         mapeamento ORM
    integrations/   Open Finance (contrato + Pluggy + Belvo + manual)
  db/migrations/    DDL versionada em SQL puro (0004 = a taxonomia da família)
  db/samples/       o mesmo extrato fictício em OFX, CSV e PDF
mobile/
  src/screens/      uma tela por módulo do sistema
  src/components/   Sankey em SVG e blocos visuais
docs/
  testando-o-sistema.md   passo a passo do zero até o IR calculado
  arquitetura.md          decisões de projeto e por quê
  importando-extratos.md  formatos aceitos e como a deduplicação funciona
  seguranca.md            o que está protegido e o que falta antes de dado real
  rodando-no-celular.md   como testar no seu aparelho pelo Expo Go
  perguntas-abertas.md    o que ainda precisa ser definido
```

## Princípios que valem para todo o código

1. **Dinheiro é `Decimal`/`numeric`, nunca `float`.** Centavo perdido em
   arredondamento binário é bug de confiança.
2. **Nenhuma alíquota, faixa ou limite fiscal vive no código.** Tudo sai de
   `tax_brackets` e `tax_parameters`, versionados por ano-calendário: a virada
   de ano é um `INSERT`, não um deploy.
3. **O que o motor não souber, ele não inventa.** Sem tabela cadastrada, a API
   devolve erro explícito em vez de calcular zero em silêncio; ano com
   parâmetros não conferidos volta marcado como `PROVISORIO`.
4. **A conciliação nunca duplica.** `provider_tx_id` tem índice único por conta
   e o lançamento manual é casado com o do banco em vez de virar linha nova.
5. **Credencial bancária não passa pela nossa base.** O provedor guarda o
   vínculo; só persistimos o id do item e a validade do consentimento.
