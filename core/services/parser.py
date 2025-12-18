from datetime import datetime, timezone
from typing import Any, Iterable

from models.participants import (
    Participant,
    ParticipantsExport,
    ParticipantType,
)
from models.telegram_message import (
    TelegramComplexText,
    TelegramMessage,
    TelegramMessages,
)


def parse_messages_raw(export_json: dict[str, Any]) -> TelegramMessages:
    messages_data = export_json.get('messages', [])
    return [TelegramMessage.model_validate(msg) for msg in messages_data]


def export_participants(messages: TelegramMessages) -> ParticipantsExport:
    participants_dict: dict[str, Participant] = {}

    def add_participant(
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

    def handle_message(msg: TelegramMessage) -> None:
        from_id_type = (
            ParticipantType.CHANNEL
            if _is_channel(msg.from_id)
            else ParticipantType.AUTHOR
        )
        forwarded_id_type = (
            {ParticipantType.CHANNEL, ParticipantType.FORWARDED_FROM}
            if _is_channel(msg.forwarded_from_id)
            else ParticipantType.FORWARDED_FROM
        )
        actor_id_type = (
            {ParticipantType.CHANNEL, ParticipantType.ACTOR}
            if _is_channel(msg.actor_id)
            else ParticipantType.ACTOR
        )
        add_participant(
            user_id=msg.from_id,
            username=None,
            full_name=msg.from_,
            p_type=from_id_type,
        )

        add_participant(
            user_id=msg.actor_id,
            username=None,
            full_name=msg.actor,
            p_type=actor_id_type,
        )

        add_participant(
            user_id=msg.forwarded_from_id,
            username=None,
            full_name=msg.forwarded_from,
            p_type=forwarded_id_type,
        )

        if isinstance(msg.text, Iterable):
            for part in msg.text:
                if (
                    isinstance(part, TelegramComplexText)
                    and part.type == 'mention'
                ):
                    username = part.text
                    add_participant(
                        user_id=None,
                        username=username,
                        full_name=None,
                        p_type=ParticipantType.MENTION,
                    )

        if not msg.reactions:
            return
        for reaction in msg.reactions:
            if not reaction.recent:
                return
            for recent in reaction.recent:
                add_participant(
                    user_id=recent.actor_id,
                    username=recent.actor,
                    full_name=None,
                    p_type=ParticipantType.REACTION,
                )

    for msg in messages:
        handle_message(msg)

    return ParticipantsExport(
        exported_at=datetime.now(timezone.utc),
        participants=list(participants_dict.values()),
    )


def _is_channel(actor_id: str | None) -> bool:
    if not actor_id:
        return False
    return actor_id.startswith('channel')
