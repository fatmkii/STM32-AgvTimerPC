from agv_timer.protocol import MAX_TIMESTAMP, LineParser, MessageKind, parse_frame


def test_parse_valid_frames() -> None:
    assert parse_frame(b"START,1234\r\n").kind is MessageKind.START
    assert parse_frame(b"EVENT,0\r\n").timestamp_ms == 0
    assert parse_frame(f"END,{MAX_TIMESTAMP}\r\n".encode()).kind is MessageKind.END


def test_invalid_frames_are_ignored() -> None:
    invalid = (
        b"START,1\n",
        b"START,1\r\nextra",
        b"UNKNOWN,1\r\n",
        b"EVENT,-1\r\n",
        b"EVENT,1.0\r\n",
        b"EVENT,18446744073709551616\r\n",
        b"EVENT,1,2\r\n",
    )
    for frame in invalid:
        assert parse_frame(frame) is None


def test_line_parser_handles_partial_and_multiple_frames() -> None:
    parser = LineParser()
    assert parser.feed(b"START,123\r") == []
    messages = parser.feed(b"\nEVENT,456\r\nEND,789\r\n")
    assert [(message.kind, message.timestamp_ms) for message in messages] == [
        (MessageKind.START, 123),
        (MessageKind.EVENT, 456),
        (MessageKind.END, 789),
    ]


def test_bad_line_does_not_block_following_valid_line() -> None:
    parser = LineParser()
    messages = parser.feed(b"bad line\nEVENT,42\r\n")
    assert len(messages) == 1
    assert messages[0].kind is MessageKind.EVENT
