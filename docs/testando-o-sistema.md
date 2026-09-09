# Passo a passo para testar o sistema

Roteiro completo, do zero até ver o Imposto de Renda calculado. Leva uns 30
minutos na primeira vez. Nada aqui exige contratar serviço nenhum.

Existem dois caminhos. Faça o **A** se quiser ver o app no celular; faça o **B**
se quiser só conferir se as contas fecham, direto do navegador.

---

## Antes de começar

Instale no computador:

- **Docker Desktop** — https://docker.com (sobe o banco e a API)
- **Node.js 20+** — https://nodejs.org (só para o caminho A)

E no celular, o app **Expo Go** (App Store / Play Store), com o aparelho na
**mesma rede Wi-Fi** do computador.

---

## Passo 1 — Subir a API e o banco

```bash
git clone https://github.com/belugaferrari/BBBC.git
cd BBBC
cp backend/.env.example backend/.env
docker compose up --build
```

Na primeira vez demora alguns minutos (está baixando PostgreSQL e Python).
Deixe esse terminal aberto — é o servidor rodando.

**Confira:** abra `http://localhost:8000/docs` no navegador. Tem que aparecer a
documentação da API, com a lista de endpoints.

## Passo 2 — Criar a família e os logins

Em **outro terminal**, na mesma pasta:

```bash
docker compose exec api python -m app.cli seed-family \
  --name "Familia BBBC" \
  --titular "Felipe"   --titular-email felipe@exemplo.com   --titular-password "senha-de-teste" \
  --conjuge "Clarissa" --conjuge-email clarissa@exemplo.com --conjuge-password "outra-senha" \
  --dependente "Filha mais velha" --dependente "Filha mais nova"
```

Sai algo como `familia criada: 3f2a…`. Isso cria os dois logins, cadastra as
filhas como dependentes (o que o IR precisa) e copia as 90 categorias da
taxonomia para a sua família.

> Use senhas de teste aqui. Quando for valer, troque — e leia
> `docs/seguranca.md` antes de colocar dado real.

---

# Caminho A — no celular

## Passo 3 — Rodar o app

```bash
cd mobile
npm install          # demora uns 2 minutos na primeira vez
npm start
```

Aparece um QR code. No **Android**, abra o Expo Go e escaneie por dentro dele.
No **iPhone**, escaneie com a câmera nativa.

## Passo 4 — Entrar

Login `felipe@exemplo.com`, senha `senha-de-teste`.

O app descobre sozinho o endereço da API. Se der "não consegui falar com o
servidor", toque em **Configurar servidor** e digite o IP do seu computador com
a porta: `192.168.0.10:8000` (troque pelo seu — no Mac/Linux, `ifconfig`; no
Windows, `ipconfig`).

## Passo 5 — Criar uma conta

Sem conta cadastrada não há onde lançar nada. Hoje isso é feito pela API:
abra `http://localhost:8000/docs`, vá em **POST /api/v1/accounts** →
*Try it out*. Antes, autorize: botão **Authorize** no topo, usuário
`felipe@exemplo.com`, senha `senha-de-teste`.

Corpo:

```json
{ "name": "Conta corrente", "type": "CONTA_CORRENTE", "is_shared": true }
```

## Passo 6 — Importar um extrato de exemplo

O repositório traz o mesmo extrato fictício em três formatos, em
`backend/db/samples/`. Mande um deles para o celular (e-mail, WhatsApp, Google
Drive — tanto faz, é só chegar nos arquivos do aparelho).

No app, aba **Importar extrato**:

1. escolha a conta;
2. **Escolher arquivo** e selecione o `extrato-exemplo.ofx`;
3. aparecem **5 lançamentos** para conferência, todos marcados;
4. toque em **Confirmar**.

**O que observar:** nada foi gravado antes de você confirmar. Agora importe o
`extrato-exemplo.csv` — é o mesmo período em outro formato. Os 5 lançamentos
aparecem **desmarcados**, com "já importado em outro formato". Confirme mesmo
assim: continuam sendo 5 lançamentos, não 10.

## Passo 7 — Ver o dinheiro andando

Aba **Resumo**:

- entrou R$ 43.000,00, saiu R$ 11.925,90, sobrou R$ 31.074,10;
- o **gráfico em cascata** mostra o pró-labore e a distribuição de lucros
  entrando à esquerda e as despesas saindo à direita;
- alterne **Família / Só eu** no canto superior.

> O mês de referência é o atual. Os exemplos são de agosto de 2026 — se hoje
> for outro mês, o resumo aparece vazio. Nesse caso importe e depois lance algo
> manualmente no mês corrente, ou consulte pela API com
> `GET /api/v1/dashboard?month=2026-08-01`.

## Passo 8 — Categorizar e ver o sistema aprender

Aba **Gastos**. Os lançamentos importados vieram sem categoria (ainda não
existe nenhuma regra).

1. toque em **BAMBU LAB STORE**;
2. escolha *Impressão 3D (Bambu Lab)*;
3. pronto — isso virou uma regra de fornecedor.

Agora lance uma compra nova do mesmo fornecedor (pela API, **POST
/api/v1/transactions**, descrição `COMPRA CARTAO BAMBU LAB FILAMENTO PETG`).
Ela entra **já categorizada**. É o aprendizado funcionando.

Categorize também:
- `PRO LABORE CHECKMOTOR` → Receitas › Ativa Fixa › Pró-labore
- `DISTRIBUICAO LUCROS` → Receitas › Ativa Variável › Distribuição de lucros
- `COLEGIO SAO JOSE` → Despesas › Essenciais › Educação › Mensalidade escolar
- `SUPERMERCADO ANGELONI` → Despesas › Essenciais › Alimentação › Supermercado

## Passo 9 — Ver o IR se montar sozinho

Aba **Imposto de Renda**. Sem você ter preenchido nada de imposto:

- **Tributável: R$ 28.000,00** — o pró-labore;
- **Isento: R$ 15.000,00** — a distribuição de lucros;
- **Deduções**: a mensalidade escolar entra limitada ao teto anual por pessoa,
  e as duas filhas aparecem como dependentes;
- **Completo × Simplificado** com a recomendação e quanto ela economiza.

Isso vem da taxonomia: cada categoria já sabe se é tributável, isenta ou
dedutível. Você categoriza o gasto uma vez, e o IR se monta.

> Vai aparecer um aviso de que os parâmetros de 2026 são provisórios. É de
> propósito — veja o item 1.7 de `docs/perguntas-abertas.md`.

## Passo 10 — Meta e teto

**Meta** (aba Previsões, ou `POST /api/v1/goals`):

```json
{
  "name": "Viagem Disney",
  "target_amount": "120000.00",
  "target_date": "2029-01-01",
  "current_amount": "15000.00",
  "monthly_contribution": "1000.00",
  "expected_annual_rate": "0.10",
  "inflation_indexed": true
}
```

O app mostra que R$ 1.000/mês não chega e **quanto falta por mês**. O campo de
simulação recalcula na hora.

**Teto** (`POST /api/v1/budget-caps`), com o id de uma categoria:

```json
{ "category_id": "…", "amount": "2000.00" }
```

No Resumo, a barra fica vermelha quando o ritmo do mês projeta estouro — não só
quando já estourou.

---

# Caminho B — sem celular, só pelo navegador

Todo o passo a passo acima funciona por `http://localhost:8000/docs`, que é uma
interface completa da API. Clique em **Authorize**, entre com
`felipe@exemplo.com` / `senha-de-teste`, e use nesta ordem:

| Ordem | Endpoint | Para quê |
|---|---|---|
| 1 | `POST /api/v1/accounts` | criar a conta |
| 2 | `POST /api/v1/imports` | enviar `backend/db/samples/extrato-exemplo.ofx` |
| 3 | `POST /api/v1/imports/{id}/confirm` | corpo `{}` grava o que veio marcado |
| 4 | `GET /api/v1/dashboard?month=2026-08-01` | fluxo do mês e dados do Sankey |
| 5 | `GET /api/v1/categories` | pegar os ids das categorias |
| 6 | `PATCH /api/v1/transactions/{id}` | categorizar (e ensinar a regra) |
| 7 | `GET /api/v1/tax/2026` | apuração do IR |
| 8 | `POST /api/v1/tax/2026/simulate-deduction` | "vale a pena guardar esse recibo?" |

## Rodar a bateria de testes

Prova que as regras estão certas sem depender de tela:

```bash
docker compose exec api python -m pytest -q
```

São 103 testes: motor de IR, simulador de metas, categorização, geometria do
Sankey, leitura dos três formatos de extrato, autorização entre famílias e o
fluxo completo de importação.

---

## Se algo não funcionar

| Sintoma | Quase sempre é |
|---|---|
| `docker compose up` falha na porta 5432 | Já existe um PostgreSQL rodando na máquina. Pare-o ou troque a porta no `docker-compose.yml`. |
| QR code abre mas o app trava | Celular e computador em redes diferentes (uma no Wi-Fi de visitantes). |
| "Não consegui falar com o servidor" | Firewall bloqueando a porta 8000, ou o IP errado em **Configurar servidor**. |
| Resumo vazio depois de importar | Os exemplos são de agosto/2026. Consulte com `?month=2026-08-01`. |
| "sem parâmetros fiscais cadastrados" | O ano-calendário não está na tabela. Só 2025 e 2026 vêm semeados. |
| Importação de PDF não reconhece nada | PDF escaneado (imagem) não tem texto. Peça OFX ou CSV ao banco. |

## Como apagar tudo e recomeçar

```bash
docker compose down -v    # -v apaga também o banco
docker compose up --build
```
