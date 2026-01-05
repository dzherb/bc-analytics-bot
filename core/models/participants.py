from datetime import datetime
import enum

from pydantic import BaseModel, Field


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

    about: str | None = None
    registered_at: datetime | None = None

    seen_as: set[ParticipantType] = Field(default_factory=set)

    def __hash__(self) -> int:
        return hash((self.user_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Participant):
            return NotImplemented
        return self.user_id == other.user_id


type ParticipantList = list[Participant]


class ParticipantsReport(BaseModel):
    exported_at: datetime
    participants: ParticipantList
