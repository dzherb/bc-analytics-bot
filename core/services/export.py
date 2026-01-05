import pandas as pd

from models.participants import ParticipantsReport

EXPORT_COLUMNS = [
    'Username',
    'Имя и фамилия',
    'Описание',
    'Дата регистрации',
    'Наличие канала в профиле',
]


def _normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    return username if username.startswith('@') else f'@{username}'


def _build_participants_dataframe(
    participants_report: ParticipantsReport,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for participant in participants_report.participants:
        is_channel = (participant.user_id or '').startswith('channel') or any(
            pt.value == 'channel' for pt in participant.seen_as
        )

        rows.append(
            {
                'Username': _normalize_username(participant.username),
                'Имя и фамилия': participant.full_name,
                'Описание': participant.about,
                'Дата регистрации': (
                    participant.registered_at.date().isoformat()
                    if participant.registered_at is not None
                    else None
                ),
                'Наличие канала в профиле': 'Да' if is_channel else 'Нет',
            }
        )

    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


def export_excel(
    participants_report: ParticipantsReport,
    file_path: str,
) -> None:
    export_date = (
        participants_report.exported_at.date().isoformat()
        if participants_report.exported_at
        else ''
    )

    df = _build_participants_dataframe(participants_report)

    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, startrow=1)

        worksheet = next(iter(writer.sheets.values()))
        worksheet.cell(row=1, column=1).value = 'Дата экспорта'
        worksheet.cell(row=1, column=2).value = export_date


def export_csv(
    participants_report: ParticipantsReport,
    file_path: str,
    *,
    encoding: str = 'utf-8',
    sep: str = ',',
) -> None:
    export_date = (
        participants_report.exported_at.date().isoformat()
        if participants_report.exported_at
        else ''
    )

    df = _build_participants_dataframe(participants_report)

    with open(file_path, 'w', encoding=encoding, newline='') as f:
        f.write(f'Дата экспорта{sep}{export_date}\n')
        df.to_csv(f, index=False, sep=sep)
