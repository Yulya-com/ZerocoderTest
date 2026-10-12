"""Точка входа: запуск чат-бота «Алина» для сообщества ВКонтакте."""

import logging
import sys

from bot.gigachat_client import GigaChatClient
from bot.knowledge import build_system_prompt, load_knowledge
from bot.vk_bot import ZerocoderVkBot
from config import ConfigError, load_config


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        print("\nПодсказка: скопируйте .env.example в .env и заполните значения.", file=sys.stderr)
        return 1

    setup_logging(config.log_level)
    logger = logging.getLogger("main")
    logger.info("Модель GigaChat: %s", config.gigachat_model)

    knowledge = load_knowledge(config.knowledge_dir)
    if not knowledge:
        logger.warning("База знаний пуста — бот будет отвечать без данных о курсах.")

    system_prompt = build_system_prompt(
        config.system_prompt_path, knowledge, config.manager_form_url
    )
    logger.info("Системный промпт собран: %d символов", len(system_prompt))

    gigachat = GigaChatClient(
        auth_key=config.auth_key,
        scope=config.gigachat_scope,
        base_url=config.gigachat_base_url,
        oauth_url=config.gigachat_oauth_url,
        model=config.gigachat_model,
        verify_ssl=config.gigachat_verify_ssl,
        ca_bundle=config.gigachat_ca_bundle,
        temperature=config.gigachat_temperature,
    )

    bot = ZerocoderVkBot(config, gigachat, system_prompt)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя.")
    finally:
        gigachat.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
