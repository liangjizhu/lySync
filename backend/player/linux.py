"""
Linux MPRIS2 player backend.

Strategy (in order):
1. playerctl subprocess — works for snap Spotify after `sudo snap connect spotify:spotify-mpris`
2. dbus-next signal listener — passively receives PropertiesChanged broadcasts (no AppArmor issue)
3. dbus-next Properties.Get — works for non-sandboxed players (VLC, Rhythmbox, etc.)
"""
import asyncio
import json
import shutil
import time
import xml.etree.ElementTree as ET
from typing import Callable, Optional

from dbus_next.aio import MessageBus
from dbus_next import BusType, MessageType
from dbus_next.introspection import Node

from .base import BasePlayer, TrackInfo

MPRIS_PREFIX = "org.mpris.MediaPlayer2"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

_PROPS_XML = Node.from_xml(ET.fromstring("""<node>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg direction="in" type="s" name="interface_name"/>
      <arg direction="in" type="s" name="property_name"/>
      <arg direction="out" type="v" name="value"/>
    </method>
  </interface>
</node>"""), is_root=True)

_DBUS_XML = Node.from_xml(ET.fromstring("""<node>
  <interface name="org.freedesktop.DBus">
    <method name="ListNames">
      <arg direction="out" type="as" name="names"/>
    </method>
  </interface>
</node>"""), is_root=True)

HAS_PLAYERCTL = shutil.which("playerctl") is not None


# ── playerctl helpers ─────────────────────────────────────────────────────────

async def _pc(*args) -> str:
    proc = await asyncio.create_subprocess_exec(
        "playerctl", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


async def _pc_track() -> Optional[TrackInfo]:
    """Read current track via playerctl."""
    try:
        status = await _pc("status")
        if status not in ("Playing", "Paused"):
            return None
        title  = await _pc("metadata", "title")
        artist = await _pc("metadata", "artist")
        album  = await _pc("metadata", "album")
        pos_s  = await _pc("position")
        length_us = await _pc("metadata", "mpris:length")
        pos_ms = int(float(pos_s) * 1000) if pos_s else 0
        dur_ms = int(length_us) // 1000 if length_us else 0
        player = await _pc("--print-name", "metadata", "--format", "{{playerName}}")
        return TrackInfo(
            title=title or "Unknown",
            artist=artist or "Unknown",
            album=album or "",
            position_ms=pos_ms,
            duration_ms=dur_ms,
            player_name=player or "unknown",
        )
    except Exception:
        return None


async def _pc_position() -> int:
    try:
        pos_s = await _pc("position")
        return int(float(pos_s) * 1000)
    except Exception:
        return 0


# ── dbus-next helpers ─────────────────────────────────────────────────────────

def _parse_metadata(meta: dict) -> tuple[str, str, str, int]:
    def get(key: str, default="") -> str:
        val = meta.get(key)
        if val is None:
            return default
        v = val.value if hasattr(val, "value") else val
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v)

    title  = get("xesam:title", "Unknown")
    artist = get("xesam:artist", "Unknown")
    album  = get("xesam:album", "")
    lus    = meta.get("mpris:length")
    dur_ms = 0
    if lus is not None:
        v = lus.value if hasattr(lus, "value") else lus
        dur_ms = int(v) // 1000
    return title, artist, album, dur_ms


async def _dbus_list_mpris(bus: MessageBus) -> list[str]:
    obj   = bus.get_proxy_object("org.freedesktop.DBus", "/org/freedesktop/DBus", _DBUS_XML)
    iface = obj.get_interface("org.freedesktop.DBus")
    names = await iface.call_list_names()
    return [n for n in names if n.startswith(MPRIS_PREFIX + ".")]


async def _dbus_get_track(bus: MessageBus, name: str) -> Optional[TrackInfo]:
    try:
        obj   = bus.get_proxy_object(name, MPRIS_PATH, _PROPS_XML)
        props = obj.get_interface(PROPS_IFACE)

        sv = await props.call_get(PLAYER_IFACE, "PlaybackStatus")
        s  = sv.value if hasattr(sv, "value") else sv
        s  = s.value if hasattr(s, "value") else str(s)
        if s not in ("Playing", "Paused"):
            return None

        mv  = await props.call_get(PLAYER_IFACE, "Metadata")
        m   = mv.value if hasattr(mv, "value") else mv
        md  = m.value  if hasattr(m, "value")  else m
        pv  = await props.call_get(PLAYER_IFACE, "Position")
        pus = pv.value if hasattr(pv, "value") else pv
        pos_ms = int(pus) // 1000

        title, artist, album, dur_ms = _parse_metadata(md)
        short = name.replace(MPRIS_PREFIX + ".", "")
        return TrackInfo(title=title, artist=artist, album=album,
                         position_ms=pos_ms, duration_ms=dur_ms, player_name=short)
    except Exception:
        return None


# ── Signal-based listener (fallback for AppArmor-blocked players) ─────────────

class _SignalListener:
    """
    Passively listens to PropertiesChanged signals from all MPRIS players.
    No method calls — unaffected by AppArmor restrictions on Properties.Get.
    Position estimated via software clock from last known timestamp.
    """
    def __init__(self):
        self._track: Optional[TrackInfo] = None
        self._pos_ms: int = 0
        self._pos_time: float = 0.0
        self._playing: bool = False

    def handle_message(self, message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return
        sender = message.sender or ""
        if not sender:
            return
        if message.interface != PROPS_IFACE or message.member != "PropertiesChanged":
            return
        if len(message.body) < 2:
            return

        iface_name = message.body[0]
        if iface_name != PLAYER_IFACE:
            return

        changed: dict = message.body[1]

        status_v = changed.get("PlaybackStatus")
        if status_v is not None:
            s = status_v.value if hasattr(status_v, "value") else str(status_v)
            self._playing = (s == "Playing")

        meta_v = changed.get("Metadata")
        if meta_v is not None:
            md = meta_v.value if hasattr(meta_v, "value") else meta_v
            md = md.value if hasattr(md, "value") else md
            title, artist, album, dur_ms = _parse_metadata(md)
            short = sender.replace(MPRIS_PREFIX + ".", "").lstrip(":")
            self._track = TrackInfo(
                title=title, artist=artist, album=album,
                position_ms=0, duration_ms=dur_ms,
                player_name=short,
            )
            self._pos_ms = 0
            self._pos_time = time.monotonic()

        pos_v = changed.get("Position")
        if pos_v is not None:
            pus = pos_v.value if hasattr(pos_v, "value") else pos_v
            self._pos_ms = int(pus) // 1000
            self._pos_time = time.monotonic()

    def get_position(self) -> int:
        if not self._playing:
            return self._pos_ms
        elapsed = (time.monotonic() - self._pos_time) * 1000
        return self._pos_ms + int(elapsed)

    def get_track(self) -> Optional[TrackInfo]:
        if self._track is None:
            return None
        return TrackInfo(
            title=self._track.title,
            artist=self._track.artist,
            album=self._track.album,
            position_ms=self.get_position(),
            duration_ms=self._track.duration_ms,
            player_name=self._track.player_name,
        )


# ── Public player class ───────────────────────────────────────────────────────

class LinuxPlayer(BasePlayer):
    def __init__(self):
        self._bus: Optional[MessageBus] = None
        self._signal = _SignalListener()
        self._pos_snapshot_ms: int = 0
        self._pos_snapshot_time: float = 0.0
        self._active_name: Optional[str] = None

    async def _get_bus(self) -> MessageBus:
        if self._bus is None:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
            bus.add_message_handler(self._signal.handle_message)
            # Subscribe to PropertiesChanged signals from any MPRIS sender
            await bus.call_message(
                await _add_match(bus, f"type='signal',interface='{PROPS_IFACE}',member='PropertiesChanged'")
            )
            self._bus = bus
        return self._bus

    async def get_current_track(self) -> Optional[TrackInfo]:
        # 1. playerctl (works after snap connect)
        if HAS_PLAYERCTL:
            track = await _pc_track()
            if track:
                return track

        # 2. dbus-next direct (non-sandboxed players like VLC)
        try:
            bus = await self._get_bus()
            names = await _dbus_list_mpris(bus)
            for name in names:
                track = await _dbus_get_track(bus, name)
                if track:
                    self._active_name = name
                    return track
        except Exception:
            pass

        # 3. Signal listener (snap players after at least one PropertiesChanged fired)
        return self._signal.get_track()

    async def get_position_ms(self) -> int:
        if HAS_PLAYERCTL:
            pos = await _pc_position()
            if pos:
                return pos
        return self._signal.get_position()

    async def watch(self, on_track_change: Callable[[Optional[TrackInfo]], None]) -> None:
        await self._get_bus()  # ensure signal listener is wired
        last_key: Optional[tuple] = None
        while True:
            track = await self.get_current_track()
            key = track.cache_key() if track else None
            if key != last_key:
                last_key = key
                on_track_change(track)
            await asyncio.sleep(1.0)


async def _add_match(bus: MessageBus, rule: str):
    """Send AddMatch to DBus to receive signals matching rule."""
    from dbus_next.message import Message as Msg
    from dbus_next.constants import MessageType as MT
    from dbus_next import Variant
    msg = Msg(
        destination="org.freedesktop.DBus",
        path="/org/freedesktop/DBus",
        interface="org.freedesktop.DBus",
        member="AddMatch",
        body=[rule],
        signature="s",
    )
    return msg


if __name__ == "__main__":
    async def _test():
        player = LinuxPlayer()
        track = await player.get_current_track()
        if track:
            print(f"Playing: {track.artist} — {track.title} [{track.player_name}]")
            print(f"Position: {track.position_ms}ms / {track.duration_ms}ms")
        else:
            print("No active player found.")
            print(f"playerctl available: {HAS_PLAYERCTL}")

    asyncio.run(_test())
