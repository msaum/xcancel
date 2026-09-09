"""Convert X links and reply to new public- and private-channel messages."""

import re
from collections import OrderedDict
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from slack_sdk.errors import SlackApiError

URL_PATTERN = re.compile(r"<(?P<slack>https?://[^<>|\s]+)(?:\|[^<>]*)?>|(?P<plain>https?://[^\s<>]+)", re.IGNORECASE)
HOSTS = {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}


def convert_urls(text):
    """Return distinct mirror URLs, preserving their first appearance."""
    converted = []
    seen = set()
    for match in URL_PATTERN.finditer(text):
        url = match.group("slack") or match.group("plain")
        if match.group("plain"):
            url = url.rstrip(".,!?;:'\"")
            for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
                while url.endswith(closing) and url.count(closing) > url.count(opening):
                    url = url[:-1].rstrip(".,!?;:'\"")
        try:
            parts = urlsplit(url)
            if parts.hostname not in HOSTS or parts.username is not None or parts.password is not None:
                continue
            # Validate ports before retaining an explicit port in the original URL.
            _ = parts.port
        except ValueError:
            continue
        mirror = re.sub(r"(?<=://)(?:www\.)?(?:x\.com|twitter\.com)", "xcancel.com", url, count=1, flags=re.IGNORECASE)
        if mirror not in seen:
            seen.add(mirror)
            converted.append(mirror)
    return converted


class EventCache:
    """Bounded best-effort deduplication for a single process."""

    def __init__(self, max_entries=4096, ttl=600, clock=monotonic):
        self.entries = OrderedDict()
        self.max_entries = max_entries
        self.ttl = ttl
        self.clock = clock
        self.lock = Lock()

    def reserve(self, event_id):
        with self.lock:
            now = self.clock()
            while self.entries and next(iter(self.entries.values())) <= now - self.ttl:
                self.entries.popitem(last=False)
            if event_id in self.entries:
                return False
            self.entries[event_id] = now
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)
            return True

    def release(self, event_id):
        with self.lock:
            self.entries.pop(event_id, None)


class XCancelListener:
    def __init__(self, cache=None):
        self.cache = cache if cache is not None else EventCache()

    def handle(self, body, event, client, logger):
        if (
            event.get("channel_type") not in ("channel", "group")
            or event.get("subtype") not in (None, "file_share")
            or event.get("bot_id")
            or event.get("bot_profile")
            or not event.get("user")
        ):
            return
        event_id = body.get("event_id")
        if not event_id or not event.get("channel") or not event.get("ts"):
            return
        links = convert_urls(event.get("text") or "")
        if not links or not self.cache.reserve(event_id):
            return
        try:
            client.chat_postMessage(
                channel=event["channel"],
                thread_ts=event.get("thread_ts") or event["ts"],
                text="\n".join(f"*X-Cancel Link:* <{link}>" for link in links),
                unfurl_links=False,
                unfurl_media=False,
            )
        except SlackApiError as error:
            if getattr(error.response, "status_code", 200) >= 500:
                logger.warning("Slack reply delivery is uncertain; duplicate suppression remains active.")
            else:
                self.cache.release(event_id)
                logger.warning("Slack rejected an XCancel reply; the event may be retried.")
        except Exception:  # noqa: BLE001 - prevent SDK exception details from exposing message content
            # Keep the reservation: Slack may have accepted the request before a timeout.
            logger.warning("XCancel reply delivery is uncertain; duplicate suppression remains active.")
