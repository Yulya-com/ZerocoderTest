"""Чат-бот сообщества ВКонтакте с ответами через GigaChat."""

import logging
import re
from typing import Dict, List

from vk_api import VkApi
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

from bot.gigachat_client import GigaChatClient, GigaChatError

logger = logging.getLogger(__name__)

VK_MESSAGE_LIMIT = 4000

COMMAND_START = {"start", "начать", "начало", "привет", "здравствуйте", "help", "помощь", ""}
COMMAND_RESET = {"reset", "сброс", "очистить", "заново"}

GROUP_MENTION_RE = re.compile(r"^\[club\d+\|[^\]]+\]\s*")


class ZerocoderVkBot:
    def __init__(self, config, gigachat: GigaChatClient, system_prompt: str) -> None:
        self.config = config
        self.gigachat = gigachat
        self.system_prompt = system_prompt

        self.vk_session = VkApi(token=config.vk_group_token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, config.vk_group_id)

        self._histories: Dict[int, List[Dict[str, str]]] = {}

    # ------------------------------------------------------------------
    # Основной цикл
    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("Бот запущен. Слушаю сообщения сообщества %s...", self.config.vk_group_id)
        for event in self.longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self._handle_message(event)
            except Exception:  # noqa: BLE001 - бот не должен падать от одного сообщения
                logger.exception("Ошибка при обработке события")

    # ------------------------------------------------------------------
    # Обработка одного сообщения
    # ------------------------------------------------------------------
    def _handle_message(self, event) -> None:
        message = event.object.message
        peer_id = message["peer_id"]
        from_id = message.get("from_id", peer_id)
        text = (message.get("text") or "").strip()

        # Игнорируем сообщения от сообществ (отрицательный from_id), чтобы
        # не отвечать самим себе.
        if from_id < 0:
            return

        text = GROUP_MENTION_RE.sub("", text).strip()

        if not text:
            self._send(peer_id, "Здравствуйте! Я Алина, консультант Zerocoder. "
                                "Расскажите, какое обучение вас интересует?")
            return

        command = text.lower().lstrip("/").strip()

        if command in COMMAND_RESET:
            self._histories.pop(peer_id, None)
            self._send(peer_id, "Хорошо, начнём диалог заново. Чем я могу помочь?")
            return

        if command in COMMAND_START:
            self._histories.pop(peer_id, None)
            self._send(peer_id, self._greeting(from_id))
            return

        self._answer(peer_id, text)

    # ------------------------------------------------------------------
    # Генерация ответа
    # ------------------------------------------------------------------
    def _answer(self, peer_id: int, text: str) -> None:
        self._set_typing(peer_id)

        history = self._histories.setdefault(peer_id, [])
        messages: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        try:
            reply = self.gigachat.chat(messages)
        except GigaChatError as exc:
            logger.error("Ошибка GigaChat: %s", exc)
            self._send(
                peer_id,
                "Извините, сейчас не получилось получить ответ. "
                "Попробуйте, пожалуйста, ещё раз через минуту — "
                "или оставьте заявку, и менеджер поможет: "
                f"{self.config.manager_form_url}",
            )
            return

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        self._trim_history(history)

        self._send(peer_id, reply)

    def _trim_history(self, history: List[Dict[str, str]]) -> None:
        max_messages = max(1, self.config.max_history_turns) * 2
        if len(history) > max_messages:
            del history[:-max_messages]

    # ------------------------------------------------------------------
    # Вспомогательные методы ВК
    # ------------------------------------------------------------------
    def _greeting(self, from_id: int) -> str:
        name = self._get_first_name(from_id)
        prefix = f"Здравствуйте, {name}!" if name else "Здравствуйте!"
        return (
            f"{prefix} Я Алина, консультант онлайн-университета Zerocoder. "
            "Помогу подобрать направление обучения под вашу цель. "
            "Расскажите, что вам интересно: смена профессии, работа с "
            "нейросетями, автоматизация или что-то другое?"
        )

    def _get_first_name(self, user_id: int) -> str:
        try:
            users = self.vk.users.get(user_ids=user_id)
            if users:
                return users[0].get("first_name", "")
        except Exception:  # noqa: BLE001
            logger.debug("Не удалось получить имя пользователя %s", user_id)
        return ""

    def _set_typing(self, peer_id: int) -> None:
        try:
            self.vk.messages.setActivity(
                type="typing",
                peer_id=peer_id,
                group_id=self.config.vk_group_id,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Не удалось установить статус «печатает»")

    def _send(self, peer_id: int, text: str) -> None:
        for chunk in self._split_message(text):
            try:
                self.vk.messages.send(
                    peer_id=peer_id,
                    message=chunk,
                    random_id=0,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось отправить сообщение в %s", peer_id)

    @staticmethod
    def _split_message(text: str) -> List[str]:
        if len(text) <= VK_MESSAGE_LIMIT:
            return [text]

        chunks = []
        remaining = text
        while len(remaining) > VK_MESSAGE_LIMIT:
            split_at = remaining.rfind("\n", 0, VK_MESSAGE_LIMIT)
            if split_at == -1:
                split_at = remaining.rfind(" ", 0, VK_MESSAGE_LIMIT)
            if split_at == -1:
                split_at = VK_MESSAGE_LIMIT
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            chunks.append(remaining)
        return chunks
