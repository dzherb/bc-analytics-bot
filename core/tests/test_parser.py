from models.participants import Participant, ParticipantType
from services.parser import (
    merge_participants,
    parse_participants_export,
)


def test_extracts_authors_and_dedupes_by_user_id() -> None:
    export = {
        'messages': [
            {
                'type': 'message',
                'from': 'Alice A',
                'from_id': 'user1',
                'text': 'hello',
                'text_entities': [{'type': 'plain', 'text': 'hello'}],
            },
            {
                'type': 'message',
                'from': 'Alice A',
                'from_id': 'user1',
                'text': 'again',
                'text_entities': [{'type': 'plain', 'text': 'again'}],
            },
        ]
    }

    result = parse_participants_export(export)

    assert result.exported_at.tzinfo is not None
    assert len(result.participants) == 1
    assert result.participants[0].user_id == 'user1'
    assert result.participants[0].full_name == 'Alice A'
    assert 'author' in result.participants[0].seen_as


def test_extracts_mentions_from_text_and_entities_and_dedupes() -> None:
    export = {
        'messages': [
            {
                'type': 'message',
                'from': 'Writer',
                'from_id': 'user2',
                'text': [
                    {'type': 'plain', 'text': 'hi '},
                    {'type': 'mention', 'text': '@alice'},
                    {'type': 'plain', 'text': ' and '},
                    {'type': 'mention', 'text': '@bob'},
                ],
            }
        ]
    }

    result = parse_participants_export(export)
    usernames = {p.username for p in result.participants if p.username}

    assert '@alice' in usernames
    assert '@bob' in usernames
    # Автор + 2 упоминания
    assert len(result.participants) == 3  # noqa: PLR2004 Magic value used in comparison, consider replacing `3` with a constant variable


def test_extracts_reactors_from_reactions_recent() -> None:
    export = {
        'messages': [
            {
                'type': 'message',
                'from': 'Author',
                'from_id': 'user3',
                'text': [{'type': 'plain', 'text': 'x'}],
                'reactions': [
                    {
                        'type': 'emoji',
                        'count': 1,
                        'emoji': '👍',
                        'recent': [{'from': 'Reactor', 'from_id': 'user4'}],
                    }
                ],
            }
        ]
    }

    result = parse_participants_export(export)
    by_id = {p.user_id: p for p in result.participants if p.user_id}

    assert 'user4' in by_id
    assert by_id['user4'].full_name == 'Reactor'
    assert 'reaction' in by_id['user4'].seen_as


def test_excludes_channels_by_id_prefix() -> None:
    export = {
        'messages': [
            {
                'type': 'message',
                'from': 'Channel Name',
                'from_id': 'channel123',
                'text': [{'type': 'plain', 'text': 'x'}],
            },
            {
                'type': 'message',
                'from': 'Author',
                'from_id': 'user7',
                'text': [{'type': 'plain', 'text': 'x'}],
                'forwarded_from': 'Some Channel',
                'forwarded_from_id': 'channel999',
                'reactions': [
                    {
                        'recent': [
                            {'from': 'Channel Reactor', 'from_id': 'channel7'}
                        ]
                    }
                ],
            },
        ]
    }

    result = parse_participants_export(export)
    ids = {p.user_id for p in result.participants if p.user_id}

    assert 'user7' in ids
    assert not any((x or '').startswith('channel') for x in ids)


def test_does_not_create_empty_participant() -> None:
    export = {
        'messages': [
            {
                'type': 'message',
                'text': '',
            }
        ]
    }

    result = parse_participants_export(export)
    assert result.participants == []


def test_merges_participants() -> None:
    p1 = Participant(
        user_id='user1',
        username='@alice2',  # user_id уникальнее чем username
        full_name='Alice A',
        seen_as={ParticipantType.AUTHOR},
    )
    p2 = Participant(
        user_id='user1',
        username='@alice',
        full_name='Alice A',
        seen_as={ParticipantType.MENTION},
    )
    p3 = Participant(
        user_id='user2',
        username='@bob',
        full_name='Bob B',
        seen_as={ParticipantType.AUTHOR},
    )

    merged = merge_participants([{p1, p3}, {p2}])

    by_id = {p.user_id: p for p in merged}
    assert len(merged) == 2  # noqa: PLR2004
    assert by_id['user1'].seen_as == {
        ParticipantType.AUTHOR,
        ParticipantType.MENTION,
    }
    assert by_id['user2'].seen_as == {ParticipantType.AUTHOR}
