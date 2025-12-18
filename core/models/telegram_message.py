from pydantic import BaseModel, Field

type TelegramText = str | list[TelegramComplexText | str]


class TelegramRecentReaction(BaseModel):
    actor: str | None = Field(default=None, alias='from')
    actor_id: str | None = Field(default=None, alias='from_id')


class TelegramReaction(BaseModel):
    recent: list[TelegramRecentReaction] | None = None


class TelegramComplexText(BaseModel):
    type: str  # нас интересует mention
    text: str  # если type == mention, то здесь @username


class TelegramMessage(BaseModel):
    type: str

    from_: str | None = Field(default=None, alias='from')
    from_id: str | None = None

    actor: str | None = None
    actor_id: str | None = None

    forwarded_from: str | None = None
    forwarded_from_id: str | None = None

    text: TelegramText
    reactions: list[TelegramReaction] | None = None


type TelegramMessages = list[TelegramMessage]
