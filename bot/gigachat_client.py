"""Клиент GigaChat API: получение токена доступа и генерация ответов."""

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Обновляем токен заранее, чтобы не ловить 401 на границе срока жизни.
_TOKEN_REFRESH_MARGIN_SEC = 60


class GigaChatError(RuntimeError):
    """Ошибка при обращении к GigaChat API."""


class GigaChatClient:
    """Минимальный HTTP-клиент GigaChat API.

    Документация:
      - токен:  POST /api/v2/oauth  (заголовки RqUID, Authorization: Basic ...)
      - генерация: POST {base_url}/chat/completions (Authorization: Bearer ...)
    """

    def __init__(
        self,
        auth_key: str,
        scope: str = "GIGACHAT_API_PERS",
        base_url: str = "https://api.giga.chat/v1",
        oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        model: str = "GigaChat-2",
        verify_ssl: bool = True,
        ca_bundle: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: int = 60,
    ) -> None:
        self.auth_key = auth_key
        self.scope = scope
        self.base_url = base_url.rstrip("/")
        self.oauth_url = oauth_url
        self.model = model
        self.temperature = temperature
        self.request_timeout = request_timeout

        if ca_bundle:
            self.verify = ca_bundle
        else:
            self.verify = verify_ssl
        if self.verify is False:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Авторизация
    # ------------------------------------------------------------------
    def _request_token(self) -> None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.auth_key}",
        }
        try:
            response = self._session.post(
                self.oauth_url,
                headers=headers,
                data={"scope": self.scope},
                timeout=self.request_timeout,
                verify=self.verify,
            )
        except requests.RequestException as exc:
            raise GigaChatError(f"Не удалось получить токен GigaChat: {exc}") from exc

        if response.status_code != 200:
            raise GigaChatError(
                f"Ошибка авторизации GigaChat (HTTP {response.status_code}): "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()
            access_token = payload["access_token"]
        except (ValueError, KeyError) as exc:
            raise GigaChatError(f"Неожиданный ответ при получении токена: {exc}") from exc

        expires_at = payload.get("expires_at", 0)
        # expires_at приходит в миллисекундах (эпоха). Приводим к секундам.
        if expires_at and expires_at > 10_000_000_000:
            expires_at = expires_at / 1000.0

        self._token = access_token
        self._token_expires_at = float(expires_at) or (time.time() + 1800)
        logger.info("Получен новый токен GigaChat, действует до %s", int(self._token_expires_at))

    def _get_token(self) -> str:
        with self._lock:
            now = time.time()
            if self._token and now < (self._token_expires_at - _TOKEN_REFRESH_MARGIN_SEC):
                return self._token
            self._request_token()
            assert self._token is not None
            return self._token

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """Отправляет историю сообщений и возвращает текст ответа модели."""
        token = self._get_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload: Dict[str, object] = {
            "model": model or self.model,
            "messages": messages,
        }

        effective_temperature = temperature if temperature is not None else self.temperature
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        if top_p is not None:
            payload["top_p"] = top_p

        url = f"{self.base_url}/chat/completions"
        try:
            response = self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
                verify=self.verify,
            )
        except requests.RequestException as exc:
            raise GigaChatError(f"Ошибка запроса к GigaChat: {exc}") from exc

        if response.status_code == 401:
            # Токен мог протухнуть — сбрасываем и пробуем ещё раз.
            with self._lock:
                self._token = None
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = self._session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout,
                    verify=self.verify,
                )
            except requests.RequestException as exc:
                raise GigaChatError(f"Ошибка запроса к GigaChat: {exc}") from exc

        if response.status_code != 200:
            raise GigaChatError(
                f"GigaChat вернул ошибку (HTTP {response.status_code}): "
                f"{response.text[:500]}"
            )

        try:
            data = response.json()
            choice = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as exc:
            raise GigaChatError(f"Неожиданный ответ GigaChat: {exc}") from exc

        if not choice or not choice.strip():
            raise GigaChatError("GigaChat вернул пустой ответ")

        return choice.strip()

    def close(self) -> None:
        self._session.close()
