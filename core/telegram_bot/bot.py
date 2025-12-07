from aiogram import Bot, Dispatcher, md
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    username = getattr(message.from_user, 'full_name', 'user')
    await message.answer(f'hello {md.bold(username)}')


@dp.message()
async def echo_handler(message: Message) -> None:
    await message.send_copy(chat_id=message.chat.id)


def provide_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
    )


def run_polling(bot: Bot) -> None:
    dp.run_polling(bot)
