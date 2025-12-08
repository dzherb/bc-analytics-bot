## Инструкция по запуску

- Создаем файл `.env` по примеру `.env.template`. Понадобится токен телеграм бота, его можно создать через [BotFather](https://t.me/BotFather) 
- Убеждаемся, что в системе установлен пакетный менеджер [uv](https://docs.astral.sh/uv/) и make (по-умолчанию идет с Linux и MacOS)
- Выполняем команду
    ```bash  
    make runserver
    ```

## Линтеры

### Запуск всех линтеров и проверок

```bash
make fullcheck
```

---

Также можно запустить проверки по-отдельности:

### Соответствие style guide

```bash
make lint
```

### Проверка типизации

```bash
make typecheck
```

### Проверка `.env` файла

```bash
make lint-dotenv
```