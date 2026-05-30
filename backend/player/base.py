from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class TrackInfo:
    title: str
    artist: str
    album: str
    position_ms: int
    duration_ms: int
    player_name: str

    def cache_key(self) -> tuple[str, str, str]:
        return (self.artist.lower(), self.title.lower(), self.album.lower())


class BasePlayer(ABC):
    @abstractmethod
    async def get_current_track(self) -> Optional[TrackInfo]: ...

    @abstractmethod
    async def get_position_ms(self) -> int: ...

    @abstractmethod
    async def watch(self, on_track_change: Callable[[Optional[TrackInfo]], None]) -> None:
        """Subscribe to track-change events. Runs indefinitely."""
        ...
