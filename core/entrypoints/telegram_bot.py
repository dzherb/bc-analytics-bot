from infra.settings import provide_settings
from telegram_bot.bot import provide_bot, run_polling


def main() -> None:
    settings = provide_settings()

    bot = provide_bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
    )

    run_polling(bot)


if __name__ == '__main__':
    main()
