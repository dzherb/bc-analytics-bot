# ruff: noqa: RUF001

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, Message

from models.participants import (
    Participant,
    ParticipantsReport,
    ParticipantType,
)
from services.export import export_excel
from services.parser import (
    export_participants,
    is_deleted_account,
    merge_participants,
    parse_messages,
)

MAX_FILES_PER_BATCH = 10
INLINE_USERNAMES_MAX_PARTICIPANTS = 50
INLINE_PARTICIPANTS_MESSAGE_MAX_LENGTH = 3800


class UploadState(StatesGroup):
    collecting = State()


dp = Dispatcher(storage=MemoryStorage())


def _escape_markdown_v2(text: str) -> str:
    escaped = text
    for ch in [
        '_',
        '*',
        '[',
        ']',
        '(',
        ')',
        '~',
        '`',
        '>',
        '#',
        '+',
        '-',
        '=',
        '|',
        '{',
        '}',
        '.',
        '!',
    ]:
        escaped = escaped.replace(ch, f'\\{ch}')
    return escaped


def _read_downloaded_bytes(downloaded: object) -> bytes:
    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)

    read = getattr(downloaded, 'read', None)
    if callable(read):
        data = read()
        if isinstance(data, str):
            return data.encode('utf-8', errors='replace')
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, bytes):
            return data

    getvalue = getattr(downloaded, 'getvalue', None)
    if callable(getvalue):
        data = getvalue()
        if isinstance(data, bytes):
            return data

    raise TypeError('Unsupported download content type')


def _normalize_username(username: str) -> str:
    username = username.strip()
    return username if username.startswith('@') else f'@{username}'


def _format_participant_details(participant: Participant) -> str:
    lines: list[str] = []

    def kv(label: str, value: str) -> str:
        return f'*{label}:* {value}'

    participant_type_ru: dict[ParticipantType, str] = {
        ParticipantType.AUTHOR: 'Автор',
        ParticipantType.MENTION: 'Упоминание',
        ParticipantType.REACTION: 'Реакция',
        ParticipantType.FORWARDED_FROM: 'Переслано от',
        ParticipantType.ACTOR: 'Действующее лицо',
        ParticipantType.SERVICE: 'Сервис',
        ParticipantType.CHANNEL: 'Канал',
    }

    if participant.user_id:
        lines.append(
            kv(
                'ID пользователя',
                _escape_markdown_v2(participant.user_id.strip()),
            )
        )

    if participant.username:
        normalized = _normalize_username(participant.username)
        lines.append(kv('Юзернейм', _escape_markdown_v2(normalized)))

    if participant.full_name:
        lines.append(
            kv('Имя', _escape_markdown_v2(participant.full_name.strip()))
        )

    if participant.about:
        lines.append(
            kv('О себе', _escape_markdown_v2(participant.about.strip()))
        )

    if participant.registered_at is not None:
        lines.append(
            kv(
                'Дата регистрации',
                _escape_markdown_v2(participant.registered_at.isoformat()),
            )
        )

    if participant.seen_as:
        seen_ru = sorted(
            (participant_type_ru.get(x, str(x)) for x in participant.seen_as)
        )
        lines.append(kv('Виден как', _escape_markdown_v2(', '.join(seen_ru))))

    if not lines:
        return _escape_markdown_v2('Неизвестный участник')

    return '\n'.join(lines)


async def _download_export_json(
    bot: Bot,
    *,
    file_id: str,
) -> dict[str, Any]:
    tg_file = await bot.get_file(file_id)
    if not tg_file.file_path:
        raise ValueError('Missing Telegram file_path')
    downloaded = await bot.download_file(tg_file.file_path)
    content_bytes = _read_downloaded_bytes(downloaded)
    parsed = json.loads(content_bytes.decode('utf-8', errors='replace'))
    if not isinstance(parsed, dict):
        raise ValueError('Expected JSON object')
    return parsed


async def _collect_participant_lists_from_files(
    bot: Bot,
    *,
    files: list[dict[str, Any]],
) -> tuple[list[list[Participant]], str | None]:
    participant_lists: list[list[Participant]] = []

    for item in files:
        file_id = item.get('file_id')
        file_name = item.get('file_name') or 'file'
        if not isinstance(file_id, str) or not file_id:
            continue

        try:
            export_json = await _download_export_json(bot, file_id=file_id)
            messages = parse_messages(export_json)
            report = export_participants(messages)
            participant_lists.append(report.participants)
        except Exception:
            return ([], str(file_name))

    return (participant_lists, None)


def _merge_filtered_participants(
    participant_lists: list[list[Participant]],
) -> list[Participant]:
    filtered_lists = [
        [p for p in part_list if not is_deleted_account(p.full_name)]
        for part_list in participant_lists
    ]
    return merge_participants(filtered_lists)


def _save_participants_excel(
    *,
    participants: list[Participant],
    export_path: Path,
    exported_at: datetime,
) -> None:
    export_excel(
        ParticipantsReport(
            exported_at=exported_at,
            participants=participants,
        ),
        str(export_path),
    )


async def _try_send_inline_participants(
    message: Message,
    *,
    participants: list[Participant],
) -> bool:
    if len(participants) > INLINE_USERNAMES_MAX_PARTICIPANTS:
        return False

    def _sort_key(p: Participant) -> tuple[int, str]:
        if p.username:
            return (0, _normalize_username(p.username).casefold())
        if p.full_name:
            return (1, p.full_name.casefold())
        return (2, (p.user_id or '').casefold())

    lines = [
        _format_participant_details(p)
        for p in sorted(participants, key=_sort_key)
    ]
    text = '\n\n'.join(lines)

    if len(text) > INLINE_PARTICIPANTS_MESSAGE_MAX_LENGTH:
        return False

    await message.answer(text)
    return True


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(UploadState.collecting)
    await state.update_data(files=[])

    text = '\n'.join(
        [
            'Пришлите историю чата одним или несколькими файлами JSON',
            (
                f'Ограничение: не более {MAX_FILES_PER_BATCH} '
                'файлов за одну обработку'
            ),
            'Когда закончите — отправьте /done',
        ]
    )
    await message.answer(_escape_markdown_v2(text))


@dp.message(Command('done'))
async def done_handler(message: Message, state: FSMContext) -> None:
    if message.bot is None:
        await message.answer(
            _escape_markdown_v2(
                'Не удалось получить доступ к боту. Повторите запрос позже.'
            ),
        )
        return
    data = await state.get_data()
    files: list[dict[str, Any]] = list(data.get('files') or [])
    if not files:
        await message.answer(
            _escape_markdown_v2(
                'Файлы не получены. Пришлите .json и отправьте /done'
            )
        )
        return

    (
        participant_lists,
        failed_file_name,
    ) = await _collect_participant_lists_from_files(
        message.bot,
        files=files,
    )
    if failed_file_name is not None:
        await state.clear()
        await message.answer(
            _escape_markdown_v2(
                f'Не удалось обработать файл: {failed_file_name}'
            )
        )
        return

    participants = _merge_filtered_participants(participant_lists)
    await state.clear()

    if await _try_send_inline_participants(message, participants=participants):
        return

    exported_at = datetime.now(timezone.utc)
    export_filename = f'participants_{exported_at.date().isoformat()}.xlsx'
    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = Path(tmpdir) / export_filename
        _save_participants_excel(
            participants=participants,
            export_path=export_path,
            exported_at=exported_at,
        )
        await message.answer_document(FSInputFile(str(export_path)))


@dp.message(F.document)
async def document_handler(message: Message, state: FSMContext) -> None:
    document = message.document
    if not document or not document.file_name:
        return

    file_name = document.file_name
    if not file_name.lower().endswith('.json'):
        await message.answer(
            _escape_markdown_v2(
                'Сейчас поддерживаются только .json — файл пропущен'
            )
        )
        return

    current_state = await state.get_state()
    if current_state is None:
        await state.set_state(UploadState.collecting)
        await state.update_data(files=[])

    data = await state.get_data()
    files: list[dict[str, Any]] = list(data.get('files') or [])

    if len(files) >= MAX_FILES_PER_BATCH:
        await message.answer(
            _escape_markdown_v2(
                (
                    f'Лимит: не более {MAX_FILES_PER_BATCH} '
                    'файлов. Отправьте /done'
                )
            ),
        )
        return

    files.append({'file_id': document.file_id, 'file_name': file_name})
    await state.update_data(files=files)
    await message.answer(
        _escape_markdown_v2(
            f'Файл принят ({len(files)}/{MAX_FILES_PER_BATCH}) /done'
        )
    )


def provide_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
    )


def run_polling(bot: Bot) -> None:
    dp.run_polling(bot)
