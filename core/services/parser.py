from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Protocol

from models.participants import (
    Participant,
    ParticipantList,
    ParticipantsReport,
    ParticipantType,
)
from models.telegram_message import (
    TelegramComplexText,
    TelegramMessage,
    TelegramMessages,
)


def merge_participants(participants: list[ParticipantList]) -> ParticipantList:
    merged_dict: dict[str, Participant] = {}

    for part_list in participants:
        for participant in part_list:
            key = participant.user_id
            if not key:
                continue

            if key not in merged_dict:
                merged_dict[key] = Participant(
                    user_id=participant.user_id,
                    username=participant.username,
                    full_name=participant.full_name,
                    seen_as=set(),
                )
            merged_dict[key].seen_as.update(participant.seen_as)

    return list(merged_dict.values())


def parse_messages(export_json: dict[str, Any]) -> TelegramMessages:
    return JsonTelegramParser().parse_obj(export_json)


def parse_participants_export(
    export_json: dict[str, Any],
) -> ParticipantsReport:
    messages = JsonTelegramParser().parse_obj(export_json)
    return ParticipantsExporter().export(messages)


def export_participants(messages: TelegramMessages) -> ParticipantsReport:
    return ParticipantsExporter().export(messages)


class TelegramParser(Protocol):
    def parse_text(self, content: str) -> TelegramMessages: ...

    def parse_bytes(
        self, content: bytes, encoding: str = 'utf-8'
    ) -> TelegramMessages: ...

    def parse_path(
        self, path: str | Path, encoding: str = 'utf-8'
    ) -> TelegramMessages: ...


class BaseTelegramParser(ABC):
    @abstractmethod
    def parse_text(self, content: str) -> TelegramMessages:
        raise NotImplementedError

    def parse_bytes(
        self, content: bytes, encoding: str = 'utf-8'
    ) -> TelegramMessages:
        return self.parse_text(content.decode(encoding, errors='replace'))

    def parse_path(
        self, path: str | Path, encoding: str = 'utf-8'
    ) -> TelegramMessages:
        file_path = Path(path)
        data = file_path.read_bytes()
        return self.parse_bytes(data, encoding=encoding)


class JsonTelegramParser(BaseTelegramParser):
    def parse_obj(self, export_json: dict[str, Any]) -> TelegramMessages:
        messages_data = export_json.get('messages', [])
        return [TelegramMessage.model_validate(msg) for msg in messages_data]

    def parse_text(self, content: str) -> TelegramMessages:
        parsed: Any = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError(
                'Expected top-level JSON object with key "messages"'
            )
        return self.parse_obj(parsed)


class ParticipantsExporter:
    @staticmethod
    def _is_channel(actor_id: str | None) -> bool:
        if not actor_id:
            return False
        return actor_id.startswith('channel')

    @staticmethod
    def _add_participant(
        participants_dict: dict[str, Participant],
        user_id: str | None,
        username: str | None,
        full_name: str | None,
        p_type: ParticipantType | set[ParticipantType],
    ) -> None:
        key = user_id or username or full_name
        if not key:
            return

        if key not in participants_dict:
            participants_dict[key] = Participant(
                user_id=user_id,
                username=username,
                full_name=full_name,
                seen_as=set(),
            )

        if isinstance(p_type, set):
            participants_dict[key].seen_as.update(p_type)
        else:
            participants_dict[key].seen_as.add(p_type)

    def export(self, messages: TelegramMessages) -> ParticipantsReport:
        participants_dict: dict[str, Participant] = {}

        def handle_message(msg: TelegramMessage) -> None:
            self._add_participant(
                participants_dict,
                user_id=msg.from_id,
                username=None,
                full_name=msg.from_,
                p_type=ParticipantType.AUTHOR,
            )

            self._add_participant(
                participants_dict,
                user_id=msg.actor_id,
                username=None,
                full_name=msg.actor,
                p_type=ParticipantType.ACTOR,
            )

            self._add_participant(
                participants_dict,
                user_id=msg.forwarded_from_id,
                username=None,
                full_name=msg.forwarded_from,
                p_type=ParticipantType.FORWARDED_FROM,
            )

            if isinstance(msg.text, list):
                for part in msg.text:
                    if (
                        isinstance(part, TelegramComplexText)
                        and part.type == 'mention'
                    ):
                        ParticipantsExporter._add_participant(
                            participants_dict,
                            user_id=None,
                            username=part.text,
                            full_name=None,
                            p_type=ParticipantType.MENTION,
                        )

            if not msg.reactions:
                return
            for reaction in msg.reactions:
                if not reaction.recent:
                    continue
                for recent in reaction.recent:
                    ParticipantsExporter._add_participant(
                        participants_dict,
                        user_id=recent.actor_id,
                        username=None,
                        full_name=recent.actor,
                        p_type=ParticipantType.REACTION,
                    )

        for msg in messages:
            handle_message(msg)

        return ParticipantsReport(
            exported_at=datetime.now(timezone.utc),
            participants=list(participants_dict.values()),
        )
