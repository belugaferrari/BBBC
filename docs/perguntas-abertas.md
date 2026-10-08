# O que ainda preciso saber

O sistema já roda inteiro com os valores assumidos abaixo — nada aqui bloqueia
o uso. O que muda com as respostas é a **precisão** (principalmente do IR) e o
quanto de configuração manual sobra para vocês.

Cada item traz o que assumi, para você só confirmar ou corrigir.

---

## 1. Fiscal — é onde a resposta vale mais

| # | Pergunta | O que assumi hoje |
|---|---|---|
| 1.1 | A Checkmotor é **Simples Nacional, Lucro Presumido ou Real**? | Não modelado. Muda se a distribuição de lucros é integralmente isenta ou se há parcela tributável. |
| 1.2 | Você retira **pró-labore de valor fixo**? Qual, e há desconto de INSS na fonte? | Categoria `Pró-labore` como tributável pela tabela; INSS lançado à parte, dedutível. |
| 1.3 | A Clarissa tem renda própria e declara **em conjunto ou separado**? | Cada membro tem apuração própria; as filhas estão como dependentes do titular. Declaração conjunta ainda não é calculada. |
| 1.4 | As **duas filhas são dependentes de quem** na declaração? | Ambas do Felipe. Se uma for da Clarissa, muda a dedução dos dois. |
| 1.5 | O **negócio de leilões** é PF ou PJ? Se PF, já recolhe carnê-leão? | Modelado como PF sujeita a carnê-leão (endpoint `/tax/{ano}/carne-leao`). |
| 1.6 | Há **imóvel alugado**, pensão judicial, PGBL ou plano de previdência? | Categorias e regras existem, sem valores. PGBL limitado a 12% da renda tributável. |
| 1.7 | **Confirmar a tabela oficial de 2026.** A regra nova (isenção ampliada + redutor progressivo) está implementada de forma parametrizada, mas as faixas de 2026 hoje são uma **cópia das de 2025** e o ano está marcado `PROVISORIO`. | Ver `db/migrations/0002_seed_catalog.sql`. Corrigir é um `INSERT`, sem deploy. |
| 1.8 | Vocês têm **contador**? Ele deveria ter acesso de leitura (papel `CONTADOR` já existe no schema)? | Sem acesso criado. |
| 1.9 | **Qual o estado e o limite anual de isenção do ITCMD** que vale para as doações da Vera e do José? | Nada preenchido, de propósito — ver abaixo. |
| 1.10 | A sua retirada da Checkmotor é **salário ou pró-labore**? Criei "Salário › Felipe" como você pediu, e o Pró-labore continua lá. | Para o **imposto de renda** os dois são tributáveis pela tabela, então o número sai igual. O que muda é o INSS, que não está modelado. |
| 1.11 | Os **dividendos da Check e da LDM são de quem** — você, a Clarissa, os dois? | Hoje a entrada é atribuída ao titular da conta onde ela cai. Cada um declara os seus, então se houver dividendo da Clarissa numa conta sua, a apuração do IR vai para o lugar errado. Ver 2.6. |

> Sobre 1.7: o motor não chuta. Ano sem tabela cadastrada devolve erro explícito
> em vez de calcular zero, e ano `PROVISORIO` volta com aviso na resposta da API.
> Nada do que sai daqui substitui a conferência do contador.

> **Sobre 1.9, porque são dois impostos e confundi-los é o erro comum.** No
> **imposto de renda** (federal) doação recebida **não paga nada**: é declarada em
> "Rendimentos Isentos e Não Tributáveis", e o sistema já leva para lá sozinho,
> pela categoria. O limite de isenção de que você se lembrava é do **ITCMD**, que
> é imposto **estadual** — a alíquota e o limite mudam de estado para estado e são
> corrigidos todo ano, e não existe um número nacional. Por isso o campo nasce
> **vazio** em Mais › Doações recebidas, e a tela avisa que ele está vazio em vez
> de vir com um número pronto: um valor chutado tranquilizaria sobre um limite que
> pode não ser o do seu estado, o que é pior que não dizer nada. Preenchido, o
> sistema soma **por doador e por ano** (é assim que o limite conta) e avisa a
> partir de 80% do teto. E a **escola continua dedutível** por quem a pagou e
> declara a dependente — receber doação isenta não tira esse direito; se os avós
> pagassem a escola direto, a dedução seria deles, e eles não declaram as meninas.
> O sistema soma e avisa: não apura nem recolhe nada.

## 2. Família, contas e privacidade

| # | Pergunta | O que assumi |
|---|---|---|
| 2.1 | **Nomes e datas de nascimento das filhas** | Cadastradas como "Filha 1" e "Filha 2". |
| 2.2 | Vocês querem ver **os gastos um do outro** por completo, ou cada um tem uma parte privada? | Visão familiar mostra tudo; o filtro "só eu" é conveniência, não privacidade. Se quiserem gasto privado de verdade, é uma regra a mais no filtro. |
| 2.3 | Quais **bancos, cartões e corretoras** entram? | Nenhum pré-cadastrado. |
| 2.4 | ~~Cartão de crédito: querem ver por **competência** (data da compra) ou por **caixa** (data da fatura)?~~ | **Respondido: por caixa.** "O valor só é contabilizado como gasto no mês em que ele efetivamente saiu da conta." A compra aparece no dia dela e conta no mês da fatura. Ver `arquitetura.md` §12. |
| 2.5 | ~~Compra parcelada deve aparecer **integral no mês da compra** ou parcela a parcela?~~ | **Respondido: parcela a parcela, em todos os meses em que ela está viva.** O leitor já lê "PARCELA 02/10" da descrição, e as parcelas que faltam viram compromisso na Previsão. |
| 2.6 | Na **conferência do extrato**, vale poder escolher o **responsável** linha a linha (hoje é sempre o titular da conta)? | Hoje não dá: o importador usa o dono da conta. Importa para o IR quando a entrada é de um e a conta é do outro. |

| 2.7b | **Estorno dentro da fatura** deveria abater o gasto do mês? | Hoje **não**: ele entra como crédito do cartão, igual ao pagamento da fatura, e não reduz o consumo. Na fatura de janeiro/2026 a diferença foi de R$ 84 em R$ 5.923 — pequena, mas é ela que separa o "comprado" (R$ 5.923,01) do "pago" (R$ 5.838,98). |
| 2.7c | **Trocar os dias da fatura** deveria recalcular os lançamentos já importados? | Hoje **não**, de propósito: boa parte deles tem o mês lido do próprio arquivo ("Vencimento 09/01/2026"), que é melhor do que qualquer conta — recalcular trocaria um dado por um palpite. Para refazer um lote, desfaça a importação e mande o arquivo de novo. |
| 2.7a | **Parcela em conta corrente**: um carnê debitado todo mês, com "1/3" na descrição, deve virar compromisso como no cartão? | Hoje **não**: só no cartão as parcelas que faltam são gravadas. Em extrato de conta corrente, "1/3" tanto pode ser carnê quanto um número que o banco escreveu por outro motivo — e inventar gastos futuros a partir de um palpite é pior que não inventar nenhum. |
| 2.7d | **O saldo do cartão vira "fatura em aberto" — e ele é acumulado, não mensal.** O número que aparecia nessa linha era tudo que já foi lançado no cartão menos tudo que foi creditado nele, desde sempre. A linha saiu da tela (as faturas que ele manda já vêm pagas), mas o **Patrimônio continua descontando esse saldo**: enquanto ele estiver errado, o patrimônio fica errado junto. Medido na fatura real de janeiro/2026: importada sozinha, ela deixa o cartão em **+R$ 850,85** (crédito a favor), porque o "Pagamento Efetuado" de R$ 6.689,83 vem dentro do próprio arquivo. Então um saldo devedor de dezenas de milhares não vem das faturas importadas inteiras — vem de cartão lançado sem o pagamento correspondente. Falta uma tela que mostre a composição do saldo de cada cartão. |
| 2.7 | **Reembolso entre amigos**: quando sobra crédito (o amigo devolveu mais do que a sua parte), isso vira o quê? | Hoje o excedente **não abate** além do valor do gasto, e fica como entrada fora da renda sem destino. Se virar comum, cabe um "a receber" de verdade — com nome de quem deve. |

## 3. Open Finance

| # | Pergunta | O que assumi |
|---|---|---|
| 3.1 | **Pluggy ou Belvo?** Já existe conta/contrato? | Os dois implementados atrás do mesmo contrato; o padrão é modo manual, sem provedor. |
| 3.2 | Sincronização **automática (webhook) ou sob demanda**? | Os dois caminhos existem; sem agendador configurado. |
| 3.3 | Quem renova o **consentimento** quando expira (até 12 meses)? | Campo `consent_expires_at` existe; falta decidir se vira alerta no app. |

## 4. Investimentos

| # | Pergunta | O que assumi |
|---|---|---|
| 4.1 | A carteira vem da **corretora via Open Finance** ou entra por planilha/manual? | Modelo suporta os dois; sem importador de planilha. |
| 4.2 | Querem **preço de mercado atualizado** (ações/FII) — de qual fonte? | Só o valor informado no snapshot; sem cotação automática. |
| 4.3 | **CDI e IPCA**: puxar do Banco Central (SGS) automaticamente? | Tabela `benchmark_series` existe e está vazia; sem carga. |
| 4.4 | Precisam de **apuração de ganho de capital** (DARF de venda de ações, isenção de R$ 20 mil/mês)? | Parâmetros cadastrados; a apuração mês a mês ainda não foi escrita. |

## 5. Metas e orçamento

| # | Pergunta | O que assumi |
|---|---|---|
| 5.1 | **Viagem à Disney**: valor-alvo, data e quanto já está guardado? | Nenhuma meta cadastrada. O simulador aceita meta corrigida pela inflação. |
| 5.2 | O fundo da meta rende quanto ao ano? | Campo por meta, começa em 0%. |
| 5.3 | Tetos por categoria: **familiares, individuais ou os dois**? | Os dois são suportados (`member_id` nulo = familiar). Nenhum teto cadastrado. |
| 5.5 | ~~A sua árvore de categorias~~ — **recebida e aplicada** (migration 0004). | Restam três pontos abertos, abaixo. |
| 5.6 | Quais são os **gastos fixos** de vocês (aluguel, escola, plano, seguros) — valor e dia do mês? | O evolutivo já lê gastos fixos cadastrados, mas ainda não há nenhum. Sem eles, a projeção usa só a média histórica, que é mais grosseira. |
| 5.4 | Querem **alerta antes de estourar** o teto (o padrão é 80%)? | 80%, configurável por teto; a projeção já avisa se o ritmo do mês estoura. |

## 5b. Taxonomia — fechada

As três pendências foram respondidas e aplicadas (migration 0005):

| # | Definido | O que virou |
|---|---|---|
| 5.7 | **Criação** é a criação das meninas | Categoria essencial, sem subdivisão. |
| 5.8 | **Anuais e Únicos ganharam filhos** | Anuais: IPVA, IPTU, Licenciamento, Seguros, Anuidades e taxas, Outros. Únicos: Móveis e eletrodomésticos, Eletrônicos, Presentes, Viagens, Reformas e reparos, Multas, Outros — **todos herdam a exigência de comentário**. |
| 5.9 | **Financiamento separa juros de amortização** | Juros, Amortização e Seguros e taxas. A amortização não conta como gasto (ver abaixo). |

**Consequência que vale saber:** a separação de juros e amortização trouxe um
conceito que faltava — nem todo dinheiro que sai da conta é gasto. Amortização é
dívida virando patrimônio, e aporte é dinheiro mudando de bolso. Os dois saem da
conta (o fluxo de caixa continua honesto), mas não entram no consumo nem
derrubam a taxa de poupança. O aporte já estava sendo contado errado antes disso
— o mesmo engano, que só apareceu quando o financiamento foi separado.

## 6. Produto e operação

| # | Pergunta | O que assumi |
|---|---|---|
| 6.1 | **iOS, Android ou os dois?** | Expo cobre os dois. |
| 6.2 | Onde a API vai rodar (VPS, Fly, Render, Cloud Run)? | Só `docker compose`; sem pipeline de deploy. |
| 6.3 | **Backup do banco** — frequência e retenção? | Não configurado. É o item que eu resolveria primeiro depois do deploy. |
| 6.4 | ~~Push notification para alertas~~ — **feito**. Falta você agendar a tarefa diária e, se quiser e-mail, configurar o SMTP. | Ver `docs/notificacoes.md`. |
| 6.6 | **Qual e-mail deve receber os avisos?** E vale a pena um para você e outro para a Clarissa? | Nenhum cadastrado. |
| 6.7 | **Você tem servidor de e-mail** ou uso o seu Gmail com senha de app? | Não configurado — sem isso, só push e a tela. |
| 6.5 | Querem **importar histórico** (OFX/CSV do banco, planilha antiga)? | Enums `IMPORT_OFX`/`IMPORT_CSV` existem; o importador não foi escrito. |

---

## Se você só puder responder três

1. **1.1 + 1.2** — regime da Checkmotor e formato da sua retirada. É o que
   define se o número do IR sai certo ou aproximado.
2. **3.1** — Pluggy ou Belvo. Sem isso, tudo entra manualmente.
3. **5.1** — os números da viagem à Disney, que é a meta que dá sentido ao
   módulo de previsões.
