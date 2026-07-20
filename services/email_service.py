"""Envio de e-mail transacional via SMTP.

Configuração via variáveis de ambiente:
  SMTP_HOST   — servidor SMTP (padrão: smtp.gmail.com)
  SMTP_PORT   — porta (padrão: 587, TLS STARTTLS)
  SMTP_USER   — endereço do remetente (ex: sistema@suaempresa.com)
  SMTP_PASS   — senha ou App Password do Google/Outlook
  APP_URL     — URL base da aplicação (padrão: http://localhost:5000)
"""
from __future__ import annotations
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
_PORT = int(os.environ.get('SMTP_PORT', 587))
_USER = os.environ.get('SMTP_USER', '')
_PASS = os.environ.get('SMTP_PASS', '')
_APP_URL = os.environ.get('APP_URL', 'http://localhost:5000').rstrip('/')


def _smtp_configurado() -> bool:
    return bool(_USER and _PASS)


def enviar_email(destinatario: str, assunto: str, html: str, texto: str = '') -> bool:
    """Envia um e-mail HTML. Retorna True em caso de sucesso."""
    if not _smtp_configurado():
        logger.warning('SMTP não configurado (SMTP_USER/SMTP_PASS ausentes). E-mail não enviado.')
        return False
    msg = MIMEMultipart('alternative')
    msg['Subject'] = assunto
    msg['From'] = _USER
    msg['To'] = destinatario
    if texto:
        msg.attach(MIMEText(texto, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        with smtplib.SMTP(_HOST, _PORT, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(_USER, _PASS)
            srv.sendmail(_USER, [destinatario], msg.as_bytes())
        logger.info(f'E-mail enviado para {destinatario}: {assunto}')
        return True
    except Exception as exc:
        logger.error(f'Falha ao enviar e-mail para {destinatario}: {exc}')
        return False


def enviar_reset_senha(destinatario: str, nome: str, token: str) -> bool:
    """Envia o e-mail de recuperação de senha com link de redefinição."""
    link = f'{_APP_URL}/redefinir-senha?token={token}'
    assunto = 'Redefinição de senha — Análise Crédito Pecuária'
    html = f'''
<!DOCTYPE html>
<html lang="pt-br">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f7f6;margin:0;padding:20px">
<div style="max-width:480px;margin:0 auto;background:white;border-radius:8px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.08)">
  <h2 style="color:#2c3e50;margin-top:0">Redefinição de senha</h2>
  <p style="color:#555;line-height:1.6">Olá, <strong>{nome}</strong>!</p>
  <p style="color:#555;line-height:1.6">
    Recebemos uma solicitação para redefinir a senha da sua conta.<br>
    Clique no botão abaixo para criar uma nova senha. O link expira em <strong>1 hora</strong>.
  </p>
  <div style="text-align:center;margin:28px 0">
    <a href="{link}"
       style="background:#2980b9;color:white;padding:12px 28px;border-radius:6px;
              text-decoration:none;font-weight:600;font-size:15px;display:inline-block">
      Redefinir minha senha
    </a>
  </div>
  <p style="color:#888;font-size:13px;line-height:1.5">
    Se você não solicitou a redefinição, ignore este e-mail — sua senha permanece a mesma.<br>
    O link expira automaticamente após 1 hora.
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
  <p style="color:#aaa;font-size:12px;text-align:center">
    Análise Crédito Pecuária
  </p>
</div>
</body>
</html>
'''
    texto = (
        f'Redefinição de senha\n\n'
        f'Olá, {nome}!\n\n'
        f'Clique no link abaixo para redefinir sua senha (válido por 1 hora):\n{link}\n\n'
        f'Se não solicitou, ignore este e-mail.'
    )
    return enviar_email(destinatario, assunto, html, texto)


def smtp_configurado() -> bool:
    return _smtp_configurado()
