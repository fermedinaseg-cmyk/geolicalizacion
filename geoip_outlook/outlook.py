"""Lectura de correos de Outlook mediante Microsoft Graph API."""

import os
from typing import Iterator, Optional

import msal
import requests

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read"]
CACHE_TOKEN = ".token_cache.json"


class ClienteOutlook:
    """Autentica con el flujo de código de dispositivo y lee el buzón del usuario.

    El token se guarda en ``.token_cache.json`` para no tener que iniciar sesión
    en cada ejecución.
    """

    def __init__(self, client_id: str, tenant: str = "consumers", cache_path: str = CACHE_TOKEN):
        self.cache_path = cache_path
        self.cache = msal.SerializableTokenCache()
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                self.cache.deserialize(f.read())
        self.app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            token_cache=self.cache,
        )
        self.sesion = requests.Session()

    def _guardar_cache(self) -> None:
        if self.cache.has_state_changed:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                f.write(self.cache.serialize())
            os.chmod(self.cache_path, 0o600)

    def token(self) -> str:
        resultado = None
        cuentas = self.app.get_accounts()
        if cuentas:
            resultado = self.app.acquire_token_silent(SCOPES, account=cuentas[0])
        if not resultado:
            flujo = self.app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flujo:
                raise RuntimeError(f"No se pudo iniciar el login: {flujo.get('error_description', flujo)}")
            print(flujo["message"], flush=True)
            resultado = self.app.acquire_token_by_device_flow(flujo)
        self._guardar_cache()
        if "access_token" not in resultado:
            raise RuntimeError(f"Error de autenticación: {resultado.get('error_description', resultado)}")
        return resultado["access_token"]

    def correos(self, busqueda: str, maximo: Optional[int] = 50) -> Iterator[dict]:
        """Itera los correos que coinciden con ``busqueda`` (sintaxis KQL de Outlook).

        Cada elemento trae: id, subject, from, receivedDateTime y body (texto plano).
        """
        cabeceras = {
            "Authorization": f"Bearer {self.token()}",
            # Pide el cuerpo en texto plano en lugar de HTML.
            "Prefer": 'outlook.body-content-type="text"',
        }
        url = f"{GRAPH}/me/messages"
        params: Optional[dict] = {
            "$search": f'"{busqueda}"',
            "$select": "id,subject,from,receivedDateTime,body",
            "$top": str(min(maximo or 50, 50)),
        }
        entregados = 0
        while url:
            r = self.sesion.get(url, headers=cabeceras, params=params, timeout=30)
            if r.status_code >= 400:
                raise RuntimeError(f"Graph API {r.status_code}: {r.text}")
            datos = r.json()
            for correo in datos.get("value", []):
                yield correo
                entregados += 1
                if maximo and entregados >= maximo:
                    return
            url = datos.get("@odata.nextLink")
            params = None  # nextLink ya incluye los parámetros
