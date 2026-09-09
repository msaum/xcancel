import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest
from slack_sdk.errors import SlackApiError

from listeners import register_listeners
from listeners.messages.xcancel import EventCache, XCancelListener, convert_urls


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See https://x.com/a/status/123", ["https://xcancel.com/a/status/123"]),
        ("http://www.twitter.com/a?x=1&y=2#part", ["http://xcancel.com/a?x=1&y=2#part"]),
        ("<https://X.COM/a?x=1&amp;y=2|a label>", ["https://xcancel.com/a?x=1&amp;y=2"]),
        ("<https://twitter.com/a>", ["https://xcancel.com/a"]),
        ("https://x.com/a https://twitter.com/a https://www.x.com/b", ["https://xcancel.com/a", "https://xcancel.com/b"]),
        ('(https://x.com/a), "https://twitter.com/b".', ["https://xcancel.com/a", "https://xcancel.com/b"]),
        ("https://x.com/a_(b)", ["https://xcancel.com/a_(b)"]),
        ("https://x.com https://twitter.com/", ["https://xcancel.com", "https://xcancel.com/"]),
        ("https://x.com.evil/a https://evil/x.com https://evilx.com https://xcancel.com/a", []),
        ("https://x.com@evil/a https://user@x.com/a https://mobile.twitter.com/a", []),
        ("https://x.com:bad/a https://[invalid/a", []),
        ("No links ftp://x.com/a", []),
    ],
)
def test_convert_urls(text, expected):
    assert convert_urls(text) == expected


@pytest.fixture
def setup_listener():
    return XCancelListener(), Mock(), logging.getLogger("test-xcancel")


def deliver(setup_listener, **changes):
    listener, client, logger = setup_listener
    event = {
        "channel_type": "channel",
        "channel": "C1",
        "ts": "123.45",
        "user": "U1",
        "text": "https://x.com/a https://twitter.com/b",
    }
    event.update(changes)
    listener.handle(body={"event_id": "Ev1"}, event=event, client=client, logger=logger)
    return client


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_reply(setup_listener, channel_type):
    client = deliver(setup_listener, channel_type=channel_type)
    client.chat_postMessage.assert_called_once_with(
        channel="C1",
        thread_ts="123.45",
        text="*X-Cancel Link:* <https://xcancel.com/a>\n*X-Cancel Link:* <https://xcancel.com/b>",
        unfurl_links=False,
        unfurl_media=False,
    )


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_thread_reply(setup_listener, channel_type):
    assert (
        deliver(setup_listener, channel_type=channel_type, thread_ts="100.0").chat_postMessage.call_args.kwargs["thread_ts"]
        == "100.0"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"subtype": "message_changed"},
        {"subtype": "message_deleted"},
        {"subtype": "bot_message"},
        {"bot_id": "B1"},
        {"bot_profile": {"id": "B1"}},
        {"user": None},
        {"channel_type": None},
        {"channel_type": "im"},
        {"channel_type": "mpim"},
        {"text": "hello"},
        {"text": "https://xcancel.com/a"},
        {"channel": None},
        {"ts": None},
    ],
)
@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_ignore(setup_listener, changes, channel_type):
    deliver(setup_listener, **({"channel_type": channel_type} | changes)).chat_postMessage.assert_not_called()


def test_file_share_with_link(setup_listener):
    deliver(setup_listener, subtype="file_share").chat_postMessage.assert_called_once()


def test_repeated_event(setup_listener):
    deliver(setup_listener)
    deliver(setup_listener).chat_postMessage.assert_called_once()


def test_confirmed_failure_releases_event(setup_listener, caplog):
    client = setup_listener[1]
    client.chat_postMessage.side_effect = SlackApiError("secret message", {"ok": False, "error": "secret token"})
    deliver(setup_listener)
    client.chat_postMessage.side_effect = None
    deliver(setup_listener)
    assert client.chat_postMessage.call_count == 2
    assert "secret" not in caplog.text


def test_uncertain_failure_keeps_event(setup_listener, caplog):
    setup_listener[1].chat_postMessage.side_effect = TimeoutError("secret token")
    deliver(setup_listener)
    deliver(setup_listener).chat_postMessage.assert_called_once()
    assert "secret" not in caplog.text


def test_cache_expiry_and_capacity():
    now = [0]
    cache = EventCache(max_entries=2, ttl=10, clock=lambda: now[0])
    assert cache.reserve("a")
    assert not cache.reserve("a")
    assert cache.reserve("b")
    assert cache.reserve("c")
    assert list(cache.entries) == ["b", "c"]
    now[0] = 10
    assert cache.reserve("b")
    assert list(cache.entries) == ["b"]


def test_cache_atomic_reservation():
    cache = EventCache()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(cache.reserve, ["same"] * 40))
    assert sum(results) == 1


def test_registration():
    app = Mock()
    register_listeners(app)
    app.event.assert_called_once_with("message")
    assert callable(app.event.return_value.call_args.args[0])


def test_server_failure_keeps_event(setup_listener):
    from slack_sdk.web.slack_response import SlackResponse

    response = SlackResponse(
        client=None, http_verb="POST", api_url="", req_args={}, data={"ok": False}, headers={}, status_code=503
    )
    setup_listener[1].chat_postMessage.side_effect = SlackApiError("unavailable", response)
    deliver(setup_listener)
    deliver(setup_listener).chat_postMessage.assert_called_once()


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_bolt_dispatch(channel_type):
    from slack_bolt import App
    from slack_bolt.request import BoltRequest
    from slack_sdk import WebClient

    client = WebClient(token="xoxb-test")
    from slack_sdk.web.slack_response import SlackResponse

    client.auth_test = Mock(
        return_value=SlackResponse(
            client=client,
            http_verb="POST",
            api_url="",
            req_args={},
            data={"ok": True, "team_id": "T1", "user_id": "UBOT", "bot_id": "B1"},
            headers={},
            status_code=200,
        )
    )
    client.chat_postMessage = Mock(return_value={"ok": True})
    app = App(client=client, process_before_response=True)
    register_listeners(app)
    request = BoltRequest(
        mode="socket_mode",
        body={
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev-bolt",
            "event": {
                "type": "message",
                "channel_type": channel_type,
                "channel": "C1",
                "user": "U1",
                "ts": "123.45",
                "text": "https://x.com/a",
            },
        },
    )
    with patch.object(WebClient, "chat_postMessage", return_value={"ok": True}) as post:
        assert app.dispatch(request).status == 200
        post.assert_called_once()
