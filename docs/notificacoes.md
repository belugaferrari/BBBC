# Avisos: como chegam até você

O sistema vigia três coisas sozinho:

- **extrato que não chegou** — de quais bancos falta o extrato do mês;
- **conta a vencer** — com a antecedência que você definir, por conta;
- **pontos a expirar** — com 60 dias de folga, porque resgate de milha não se
  faz na véspera.

## Onde o aviso aparece

| Canal | Funciona | O que precisa |
|---|---|---|
| **Dentro do app** | sempre | nada |
| **Push no celular** | iPhone e Android | autorizar quando o app pedir |
| **E-mail** | qualquer aparelho, inclusive o computador | um servidor SMTP configurado |

### Sobre "avisar no computador", sem rodeio

Não existe um canal nativo de Windows aqui. Um alerta na barra de tarefas
exigiria um programa instalado rodando em segundo plano — outro projeto, não uma
opção de configuração.

O que chega ao computador são dois caminhos:

- **e-mail** — é o único que funciona com o computador desligado na hora do
  aviso, e o que eu recomendo;
- **push do Expo**, que também entrega na versão web do app, quando ela está
  aberta no navegador.

## Configurando o e-mail

No `backend/.env`:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=a-senha-de-app
SMTP_FROM=seu-email@gmail.com
```

> **Com Gmail, use uma "senha de app"**, não a sua senha real: Conta Google →
> Segurança → Verificação em duas etapas → Senhas de app. A senha de app pode
> ser revogada sozinha, sem trocar a sua senha de verdade.

Sem SMTP configurado o canal fica **indisponível** — e o sistema diz isso, em vez
de fingir que enviou. Os avisos ficam na fila esperando a configuração.

## Push no celular

Não precisa de nada configurado. Na primeira vez que você entra no app, ele pede
a permissão e registra o aparelho sozinho. Se você recusar, o app continua
funcionando — só sem aviso no celular.

Duas coisas a saber: **push não funciona em emulador**, só em aparelho de
verdade; e cada aparelho é um registro, então o seu celular e o da Clarissa
recebem os dois.

## Fazendo os avisos chegarem sozinhos

Esta é a parte que depende de você.

O sistema roda no seu computador, e um computador de casa não fica ligado o
tempo todo — então não existe um processo em segundo plano vigiando. O que
existe é um comando:

```bash
docker compose exec api python -m app.cli run-alerts
```

Ele recalcula os avisos e envia a fila. **Para rodar sozinho todo dia**, agende:

**Windows** — Agendador de Tarefas → Criar Tarefa Básica → diariamente às 8h →
Iniciar um programa:

```
Programa:   docker
Argumentos: compose -f C:\caminho\para\BBBC\docker-compose.yml exec -T api python -m app.cli run-alerts
```

**Mac/Linux** — `crontab -e` e acrescente:

```
0 8 * * * cd /caminho/para/BBBC && docker compose exec -T api python -m app.cli run-alerts
```

O app também recalcula os avisos toda vez que você abre a tela de resumo, então
mesmo sem agendador nada se perde — só chega mais tarde.

## Por que o mesmo aviso não chega duas vezes

Cada aviso tem uma **chave estável**: `vencimento:<conta>:<data>`. Rodar o
comando cinco vezes no mesmo dia não gera cinco avisos. E cada envio é
registrado por (aviso, aparelho) — se o comando for reexecutado depois de uma
falha de rede, só o que não foi entregue é tentado de novo.

Falha de envio é tentada **três vezes**. Depois disso o destino é marcado com
erro, em vez de insistir para sempre num endereço que não existe mais.
