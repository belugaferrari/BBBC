# Onde paramos

Anotado em 01/10/2026, no ponto em que o sistema abriu pela primeira vez.

## O que já funciona

O app **abre no navegador do PC** e entra com o login. Isso prova a cadeia
inteira: PostgreSQL, API, autenticação e interface. Primeira versão de fato
funcional.

---

## 1. Expo Go não abre no celular

**Sintoma:** `java.io.IOException: Failed to download remote update`.

**O que já foi eliminado:**

| | |
|---|---|
| Endereço errado (`127.0.0.1`) | **resolvido** — o terminal mostra `exp://192.168.15.57:8081` |
| SDK velho demais para o Expo Go | **resolvido** — SDK 57 |
| `expo-notifications` derrubando o app | **resolvido** — carregado sob demanda |
| `expo-secure-store` no navegador | **resolvido** — não afeta o celular |

Sobrou a **rede entre os dois aparelhos**: Firewall do Windows bloqueando o
Node, roteador isolando aparelhos (comum com celular no 5GHz e PC no cabo), ou
celular em outra rede.

**Próximo passo, ainda não tentado:** a **opção 2** do `INICIAR-APP`, que serve
o app por túnel e atravessa os três casos de uma vez. Se funcionar, confirma o
diagnóstico de rede e o celular fica resolvido sem mexer em firewall.

---

## 2. Acumular mudanças antes de publicar

O ciclo de uma correção por vez ficou lento demais: cada ajuste obrigava a
apagar a pasta, baixar o ZIP e reinstalar.

**Combinado:** daqui em diante as mudanças são construídas e validadas em
lote, e só então publicadas. Um download cobre várias correções.

Vale enquanto o sistema está na máquina de casa. Hospedado, a atualização
deixaria de passar pelo usuário.

---

## 3. O sistema ligar junto com o Windows

Hoje é preciso clicar no `ABRIR-BBBC-windows.bat` toda vez.

**A fazer:** atalho na pasta de Inicialização do Windows, para o sistema já
estar no ar quando o computador liga. O dia a dia vira abrir o Expo Go no
celular, ou um favorito no navegador — sem arquivo nenhum para clicar.

Junto disso: o launcher **lembrar a última escolha** entre 1, 2 e 3, em vez de
perguntar sempre.

---

## 4. Pendente de resposta

- **Pró-labore, lucros ou adiantamento**, quando a Checkmotor paga uma conta
  pessoal. Decide o imposto. Hoje o padrão é *adiantamento*, que é o único que
  não afirma nada sobre tributo.
- Os **gastos fixos** (financiamento, escola, plano, condomínio): valor e dia
  do mês. Sem eles a previsão depende só da média do histórico.
- Qual **e-mail** recebe os avisos.

## 5. Construído e ainda sem tela

A separação pessoal/empresa está pronta no servidor — a conta marcada como da
empresa, a triagem linha a linha na importação, o par que mantém o caixa
honesto, e as categorias das duas pontas. Falta a **lista de pendências**
("a empresa me deve") e as telas no aplicativo.
