"""Загрузка и проверка настроек бота из переменных окружения (.env)."""

import base64
import logging
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"), encoding="utf-8-sig")

logger = logging.getLogger(__name__)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Переменная %s содержит не число: %r. Использую %s", name, raw, default)
        return default


def _get_float(name: str):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("Переменная %s содержит не число: %r. Игнорирую.", name, raw)
        return None


class ConfigError(RuntimeError):
    """Ошибка конфигурации: не хватает обязательных переменных."""


class Config:
    def __init__(self) -> None:
        # ВКонтакте
        self.vk_group_token = (os.getenv("VK_GROUP_TOKEN") or "").strip()
        self.vk_group_id = _get_int("VK_GROUP_ID", 0)

        # GigaChat
        self.gigachat_auth_key = (os.getenv("GIGACHAT_AUTH_KEY") or "").strip()
        self.gigachat_client_id = (os.getenv("GIGACHAT_CLIENT_ID") or "").strip()
        self.gigachat_client_secret = (os.getenv("GIGACHAT_CLIENT_SECRET") or "").strip()
        self.gigachat_scope = (os.getenv("GIGACHAT_SCOPE") or "GIGACHAT_API_PERS").strip()
        self.gigachat_model = (os.getenv("GIGACHAT_MODEL") or "GigaChat-2").strip()
        self.gigachat_base_url = (
            os.getenv("GIGACHAT_BASE_URL") or "https://api.giga.chat/v1"
        ).strip().rstrip("/")
        self.gigachat_oauth_url = (
            os.getenv("GIGACHAT_OAUTH_URL")
            or "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        ).strip()
        self.gigachat_verify_ssl = _get_bool("GIGACHAT_VERIFY_SSL", True)
        self.gigachat_ca_bundle = (os.getenv("GIGACHAT_CA_BUNDLE") or "").strip() or None
        self.gigachat_temperature = _get_float("GIGACHAT_TEMPERATURE")

        # Чат-бот
        self.manager_form_url = (
            os.getenv("MANAGER_FORM_URL") or "https://zerocoder.ru/"
        ).strip()
        self.max_history_turns = _get_int("MAX_HISTORY_TURNS", 10)
        self.log_level = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()

        # Пути к ресурсам
        self.prompts_dir = os.path.join(BASE_DIR, "prompts")
        self.knowledge_dir = os.path.join(BASE_DIR, "knowledge")
        self.system_prompt_path = os.path.join(
            self.prompts_dir, "alina_system_prompt.txt"
        )

    @property
    def auth_key(self) -> str:
        """Возвращает ключ авторизации GigaChat (Base64 от ClientID:ClientSecret)."""
        if self.gigachat_auth_key:
            return self.gigachat_auth_key
        if self.gigachat_client_id and self.gigachat_client_secret:
            raw = f"{self.gigachat_client_id}:{self.gigachat_client_secret}"
            return base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return ""

    def validate(self) -> None:
        problems = []
        if not self.vk_group_token:
            problems.append("VK_GROUP_TOKEN не задан")
        if not self.vk_group_id:
            problems.append("VK_GROUP_ID не задан")
        if not self.auth_key:
            problems.append(
                "не задан ключ GigaChat: укажите GIGACHAT_AUTH_KEY "
                "или пару GIGACHAT_CLIENT_ID / GIGACHAT_CLIENT_SECRET"
            )
        if not os.path.isfile(self.system_prompt_path):
            problems.append(f"не найден системный промпт: {self.system_prompt_path}")
        if problems:
            raise ConfigError(
                "Некорректная конфигурация. Проверьте файл .env:\n  - "
                + "\n  - ".join(problems)
            )


def load_config() -> Config:
    config = Config()
    config.validate()
    return config
