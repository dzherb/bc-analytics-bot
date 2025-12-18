from datetime import datetime
import enum

from pydantic import BaseModel


class ParticipantType(enum.StrEnum):
    AUTHOR = 'author'
    MENTION = 'mention'
    REACTION = 'reaction'
    FORWARDED_FROM = 'forwarded'
    ACTOR = 'actor'
    SERVICE = 'service'
    CHANNEL = 'channel'


class Participant(BaseModel):
    user_id: str | None = None
    username: str | None = None
    full_name: str | None = None

    seen_as: set[ParticipantType] = set()


class ParticipantsExport(BaseModel):
    exported_at: datetime
    participants: list[Participant]
