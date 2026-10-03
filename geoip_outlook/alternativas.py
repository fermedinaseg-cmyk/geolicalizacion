"""Lectores de correo sin Azure: IMAP (contraseña de aplicación) o carpeta de archivos .eml."""

import email
import imaplib
import os
from email import policy
from email.message import Message
from typing import Iterator


def _a_dict(msg: Message) -> dict:
    """Convierte un mensaje a la misma forma que devuelve Microsoft Graph."""
    cuerpo = msg.get_body(preferencelist=("plain", "html"))
    return {
        "subject": str(msg.get("Subject", "")),
        "from": {"emailAddress": {"address": email.utils.parseaddr(str(msg.get("From", "")))[1]}},
        "receivedDateTime": str(msg.get("Date", "")),
        "body": {"content": cuerpo.get_content() if cuerpo else ""},
    }


def correos_eml(carpeta: str, remitente: str = "", maximo: int = 50) -> Iterator[dict]:
    """Lee archivos .eml de ``carpeta`` (Outlook: arrastra los correos a una carpeta)."""
    entregados = 0
    for nombre in sorted(os.listdir(carpeta), reverse=True):
        if not nombre.lower().endswith(".eml"):
            continue
        with open(os.path.join(carpeta, nombre), "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        if remitente and remitente.lower() not in str(msg.get("From", "")).lower():
            continue
        yield _a_dict(msg)
        entregados += 1
        if maximo and entregados >= maximo:
            return


def correos_imap(servidor: str, usuario: str, clave: str, remitente: str = "binance.com",
                 maximo: int = 50, carpeta: str = "INBOX") -> Iterator[dict]:
    """Lee correos por IMAP en modo solo lectura. ``clave`` = contraseña de aplicación."""
    with imaplib.IMAP4_SSL(servidor) as imap:
        imap.login(usuario, clave)
        imap.select(carpeta, readonly=True)
        _, datos = imap.search(None, "FROM", f'"{remitente}"')
        ids = datos[0].split()[::-1][:maximo]
        for num in ids:
            _, partes = imap.fetch(num, "(BODY.PEEK[])")
            yield _a_dict(email.message_from_bytes(partes[0][1], policy=policy.default))
