"""Сборка системного промпта и базы знаний для GigaChat."""

import logging
import os

logger = logging.getLogger(__name__)

_KNOWLEDGE_EXTENSIONS = (".md", ".txt")


def load_knowledge(knowledge_dir: str) -> str:
    """Читает все файлы базы знаний (.md/.txt) из каталога и объединяет их.

    Порядок детерминированный (по имени файла), чтобы промпт был стабилен.
    """
    if not os.path.isdir(knowledge_dir):
        logger.warning("Каталог базы знаний не найден: %s", knowledge_dir)
        return ""

    files = sorted(
        name
        for name in os.listdir(knowledge_dir)
        if name.lower().endswith(_KNOWLEDGE_EXTENSIONS)
        and os.path.isfile(os.path.join(knowledge_dir, name))
    )

    if not files:
        logger.warning("В каталоге %s нет файлов базы знаний", knowledge_dir)
        return ""

    parts = []
    for name in files:
        path = os.path.join(knowledge_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
        if content:
            parts.append(content)
            logger.info("Загружен файл базы знаний: %s (%d символов)", name, len(content))

    return "\n\n---\n\n".join(parts)


def build_system_prompt(system_prompt_path: str, knowledge: str, manager_form_url: str) -> str:
    """Собирает итоговый system-промпт: инструкции + база знаний."""
    with open(system_prompt_path, "r", encoding="utf-8") as fh:
        prompt = fh.read()

    prompt = prompt.replace("{{MANAGER_FORM_URL}}", manager_form_url)

    if knowledge:
        prompt += (
            "\n\n# ================================================================\n"
            "#  БАЗА ЗНАНИЙ (единственный достоверный источник фактов)\n"
            "# ================================================================\n\n"
            + knowledge
        )

    return prompt
