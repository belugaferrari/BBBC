"""Envio dos avisos para celular e e-mail.

Sobre "avisar no computador", sem rodeio: nao existe um canal proprio de
desktop aqui. O que existe sao dois caminhos que chegam ao computador:

  * e-mail, que abre em qualquer aparelho e e o unico que funciona com o
    computador desligado na hora do aviso;
  * push do Expo, que tambem entrega na versao web do app quando ela esta
    aberta no navegador.

Um alerta nativo do Windows exigiria um programa instalado rodando em segundo
plano - outro projeto, nao uma opcao de configuracao. Ver docs/notificacoes.md.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.core.config import settings

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


@dataclass(frozen=True)
class Mensagem:
    title: str
    body: str
    severity: str = "INFO"
    data: dict | None = None


@dataclass
class Resultado:
    ok: bool
    error: str | None = None


class NotificadorIndisponivel(RuntimeError):
    """Canal sem configuracao. Nao e erro de envio: e falta de credencial."""


# ---------------------------------------------------------------------------
# Push (Expo)
# ---------------------------------------------------------------------------
def enviar_push(token: str, mensagem: Mensagem, client: httpx.Client | None = None) -> Resultado:
    """Envia pelo servico de push do Expo.

    Nao exige conta paga nem chave: o token do aparelho, que o app registra no
    primeiro login, basta. Um token invalido (`DeviceNotRegistered`) volta como
    erro para o destino poder ser desativado, em vez de tentar para sempre.
    """
    if not token.startswith("ExponentPushToken") and not token.startswith("ExpoPushToken"):
        return Resultado(False, f"token de push com formato inesperado: {token[:20]}")

    corpo = {
        "to": token,
        "title": mensagem.title,
        "body": mensagem.body,
        "sound": "default" if mensagem.severity != "INFO" else None,
        "priority": "high" if mensagem.severity == "CRITICO" else "default",
        "data": mensagem.data or {},
    }

    try:
        http = client or httpx.Client(timeout=15)
        resposta = http.post(EXPO_PUSH_URL, json=corpo)
        resposta.raise_for_status()
        dados = resposta.json().get("data", {})
        if isinstance(dados, dict) and dados.get("status") == "error":
            return Resultado(False, dados.get("message", "erro no push"))
        return Resultado(True)
    except httpx.HTTPError as exc:
        return Resultado(False, f"falha de rede no push: {exc}")
    finally:
        if client is None:
            http.close()


# ---------------------------------------------------------------------------
# E-mail (SMTP)
# ---------------------------------------------------------------------------
def enviar_email(destino: str, mensagem: Mensagem) -> Resultado:
    if not settings.smtp_host or not settings.smtp_from:
        raise NotificadorIndisponivel(
            "e-mail sem configuracao: defina SMTP_HOST, SMTP_USER, SMTP_PASSWORD "
            "e SMTP_FROM no .env"
        )

    email = EmailMessage()
    email["Subject"] = mensagem.title
    email["From"] = settings.smtp_from
    email["To"] = destino
    email.set_content(
        f"{mensagem.body}\n\n"
        "— BBBC, o sistema financeiro da familia.\n"
        "Este aviso foi gerado automaticamente."
    )

    try:
        if settings.smtp_use_ssl:
            servidor = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
        else:
            servidor = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            if settings.smtp_use_tls:
                servidor.starttls()
        with servidor:
            if settings.smtp_user:
                servidor.login(settings.smtp_user, settings.smtp_password or "")
            servidor.send_message(email)
        return Resultado(True)
    except (smtplib.SMTPException, OSError) as exc:
        return Resultado(False, f"falha no envio de e-mail: {exc}")


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------
def enviar(canal: str, endereco: str, mensagem: Mensagem) -> Resultado:
    if canal == "PUSH":
        return enviar_push(endereco, mensagem)
    if canal == "EMAIL":
        return enviar_email(endereco, mensagem)
    return Resultado(False, f"canal desconhecido: {canal}")
