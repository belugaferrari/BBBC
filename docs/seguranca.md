# Segurança — o que está feito e o que falta

Estado real do código, sem adjetivo de marketing. O app guarda o extrato
bancário e a base de cálculo do IR de vocês dois; o padrão de cuidado tem que
ser o de um app de banco, não o de um app de lista de compras.

## O que já está no código

| Item | Como está |
|---|---|
| Senha | `bcrypt` com salt por usuário, custo padrão 12. O segredo passa por SHA-256 antes, porque o bcrypt trunca em 72 bytes. A senha nunca é gravada nem logada. |
| Sessão | JWT assinado (HS256) com expiração. O app guarda no **Keychain (iOS) / Keystore (Android)** via `expo-secure-store`, não em `AsyncStorage`. |
| 401 no cliente | Token inválido ou expirado é apagado do dispositivo automaticamente. |
| **Autorização** | Todo id que chega pelo corpo ou pela query (conta, categoria, tag, membro, meta) é resolvido contra a família do token. Responde **404**, não 403: um 403 confirmaria que aquele id existe. |
| Credencial bancária | **Nunca passa pela nossa base.** O provedor de Open Finance guarda o vínculo; persistimos só o id do item e a validade do consentimento. |
| Webhook | Sem assinatura HMAC válida, o evento é gravado para auditoria e **descartado** — nunca processado. |
| SQL | Sem concatenação de string em lugar nenhum; consultas parametrizadas via SQLAlchemy. |
| Boot em produção | A API **se recusa a subir** com `SECRET_KEY` de exemplo, segredo curto ou banco em `localhost`. |
| CORS | Aberto só em desenvolvimento; em produção a lista começa vazia (você preenche com o domínio real). |

## O que falta antes de guardar dado real

Em ordem de importância:

1. **HTTPS obrigatório.** Hoje o app fala HTTP em desenvolvimento. Em produção,
   TLS na frente da API (Caddy, nginx, ou o proxy do provedor de hospedagem) e
   HSTS. Sem isso, token e extrato trafegam em claro.
2. **Backup do banco.** Não configurado. É o que eu faria primeiro depois do
   deploy: backup diário com retenção e **um teste de restauração**.
3. **Rate limiting no login.** Não implementado. Hoje nada impede tentativa
   automatizada de senha. Com dois usuários, um bloqueio simples por IP/e-mail
   resolve.
4. **CPF em claro.** A coluna existe e está sem criptografia (há um comentário
   no DDL marcando isso). Se for guardar CPF, cifrar em repouso ou não guardar.
5. **Segundo fator.** Para um app com o patrimônio da família inteira, vale um
   TOTP no login. Não está feito.
6. **Rotação de token.** O JWT dura 30 dias e não há refresh nem revogação: se
   um aparelho for perdido, hoje a saída é trocar o `SECRET_KEY` (o que desloga
   os dois).
7. **Logs.** Não há trilha de auditoria de acesso — quem viu o quê e quando.

## Checklist de deploy

```
[ ] SECRET_KEY gerado com `python -c "import secrets; print(secrets.token_urlsafe(48))"`
[ ] APP_ENV=production   (a API valida a config no boot)
[ ] TLS na frente da API, HTTP redirecionando para HTTPS
[ ] Postgres sem porta pública, senha forte, backup diário testado
[ ] CORS restrito ao domínio do app
[ ] .env fora do git (já está no .gitignore)
[ ] Webhook do provedor com secret configurado (senão todo evento é recusado)
```
