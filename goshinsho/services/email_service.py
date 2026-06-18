import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..config import Config


def is_email_configured():
    return all(
        [
            Config.AWS_ACCESS_KEY_ID,
            Config.AWS_SECRET_ACCESS_KEY,
            Config.AWS_REGION,
            Config.SES_FROM_EMAIL,
        ]
    )


def _ses_client():
    if not is_email_configured():
        raise RuntimeError("Amazon SES não está configurado. Defina AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION e SES_FROM_EMAIL no .env.")

    return boto3.client(
        "ses",
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )


def send_email(to_email, subject, text_body, html_body=None, reply_to=None):
    destination = {"ToAddresses": [to_email]}
    message_body = {"Text": {"Charset": "UTF-8", "Data": text_body}}
    if html_body:
        message_body["Html"] = {"Charset": "UTF-8", "Data": html_body}

    payload = {
        "Source": Config.SES_FROM_EMAIL,
        "Destination": destination,
        "Message": {
            "Subject": {"Charset": "UTF-8", "Data": subject},
            "Body": message_body,
        },
    }
    if reply_to:
        payload["ReplyToAddresses"] = [reply_to]

    try:
        return _ses_client().send_email(**payload)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Erro ao enviar e-mail pelo Amazon SES: {exc}") from exc


def send_contact_emails(name, email, message):
    admin_body = f"""
Nova mensagem recebida pelo formulário de contato do Goshinsho.

Nome: {name}
E-mail: {email}

Mensagem:
{message}
""".strip()

    user_body = f"""
Olá, {name}.

Recebemos sua mensagem no Goshinsho e responderemos em breve.

Sua mensagem:
{message}
""".strip()

    if Config.SES_CONTACT_TO_EMAIL:
        send_email(
            Config.SES_CONTACT_TO_EMAIL,
            "Nova mensagem de contato - Goshinsho",
            admin_body,
            reply_to=email,
        )

    send_email(
        email,
        "Recebemos sua mensagem - Goshinsho",
        user_body,
    )
