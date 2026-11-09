# Auto-play sırasında tekrar eden sanatçı ve şarkıları engelleyen filtre
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


# Başlıklardaki teknik/format gürültüsü
NOISE_WORDS = {
    "official", "video", "audio", "music", "lyric", "lyrics", "visualizer",
    "clip", "hd", "hq", "4k", "8k", "remastered", "remaster", "explicit",
    "clean", "topic", "mv",
}

# Aynı şarkının farklı sürümlerini işaret eden kelimeler
VARIANT_WORDS = {
    "remix", "remiks", "mix", "cover", "slowed", "reverb", "nightcore",
    "sped", "speed", "speedup", "extended", "edit", "instrumental",
    "karaoke", "live", "acoustic", "akustik", "bootleg", "mashup", "demo",
    "versiyon", "versiyonu", "canli", "hizlandirilmis", "yavaslatilmis",
    "düzenleme", "duzenleme",
}

UNKNOWN_ARTISTS = {
    "", "various artists", "various", "unknown", "unknown artist",
    "bilinmiyor", "youtube", "topic", "auto generated",
}

_HYPHEN_SPLIT = re.compile(r"\s+[-–—]\s+")
_BRACKET_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_FEAT_RE = re.compile(r"\b(?:feat\.?|ft\.?|featuring)\b.*$", re.IGNORECASE)
_ARTIST_SPLIT_RE = re.compile(r"\s*(?:,|&|/|\+|\s+x\s+|\s+×\s+)\s*", re.IGNORECASE)
_CHANNEL_SUFFIX_RE = re.compile(r"\s*(?:-\s*topic|vevo|official|channel)\s*$", re.IGNORECASE)
_VARIANT_TAIL_RE = re.compile(
    rf"\s+(?:{'|'.join(sorted(VARIANT_WORDS, key=len, reverse=True))})\b.*$"
)


def normalize_text(text: str) -> str:
    """Büyük/küçük harf, aksan ve noktalama farklarını ortadan kaldırır."""
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("ı", "i")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    return set(normalize_text(text).split())


def _strip_brackets(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _BRACKET_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_variant(text: str) -> bool:
    return bool(_tokens(text) & VARIANT_WORDS)


def _is_variant_only(text: str) -> bool:
    tokens = _tokens(text)
    return bool(tokens) and tokens <= (VARIANT_WORDS | NOISE_WORDS)


def _is_variant_descriptor(text: str) -> bool:
    """Sağ taraf 'Remix', 'DJ X Remix' gibi bir sürüm açıklaması mı?"""
    if _is_variant_only(text):
        return True

    tokens = normalize_text(text).split()
    if not (set(tokens) & VARIANT_WORDS):
        return False

    return bool(tokens) and tokens[0] in {"dj", "remixer", "producer"}


def split_artist_title(title: str) -> tuple[str | None, str]:
    """'Sanatçı - Şarkı' başlığını sanatçı ve şarkı adına ayırır."""
    cleaned = _strip_brackets(title or "")
    parts = _HYPHEN_SPLIT.split(cleaned)

    if len(parts) < 2:
        return None, cleaned.strip()

    artist = parts[0].strip()
    song = " - ".join(part.strip() for part in parts[1:] if part.strip())

    # Sağ taraf yalnızca bir sürüm etiketiyse sol taraf şarkının kendisidir.
    if _is_variant_descriptor(song):
        return None, artist

    return artist, song


def _clean_artist(name: str | Iterable[str] | None) -> str:
    if not name:
        return ""

    if not isinstance(name, str):
        name = ", ".join(str(part) for part in name if part)

    text = _strip_brackets(name)
    text = _FEAT_RE.sub(" ", text)
    text = _CHANNEL_SUFFIX_RE.sub(" ", text)
    text = _ARTIST_SPLIT_RE.split(text, maxsplit=1)[0]
    text = normalize_text(text)

    if text in UNKNOWN_ARTISTS:
        return ""
    return text


def extract_artist(
    title: str,
    *,
    uploader: str | None = None,
    artist: str | Iterable[str] | None = None,
) -> str:
    """Şarkıdan veya metaveriden karşılaştırılabilir sanatçı adı üretir."""
    explicit = _clean_artist(artist)
    if explicit:
        return explicit

    parsed_artist, _ = split_artist_title(title)
    cleaned = _clean_artist(parsed_artist)
    if cleaned:
        return cleaned

    return _clean_artist(uploader)


def core_title(title: str) -> str:
    """Şarkı adını; sanatçı, feat, remix ve format etiketlerinden arındırır."""
    _, song = split_artist_title(title or "")
    song = _FEAT_RE.sub(" ", song)
    song = _strip_brackets(song)

    segments = [
        segment.strip()
        for segment in _HYPHEN_SPLIT.split(song)
        if segment.strip() and not _contains_variant(segment)
    ]
    if segments:
        song = " - ".join(segments)

    normalized = normalize_text(song)
    normalized = _VARIANT_TAIL_RE.sub(" ", normalized)
    tokens = [token for token in normalized.split() if token not in NOISE_WORDS]
    return " ".join(tokens)


def is_same_song(title_a: str, title_b: str) -> bool:
    """Aynı şarkının normal, remix, cover veya live sürümü mü?"""
    core_a = core_title(title_a)
    core_b = core_title(title_b)

    if not core_a or not core_b:
        return normalize_text(title_a) == normalize_text(title_b)

    if core_a == core_b:
        return True

    tokens_a = set(core_a.split())
    tokens_b = set(core_b.split())
    if not tokens_a or not tokens_b:
        return False

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union)

    # "Song" / "Song Part 2" gibi kısa başlıklarda yanlış eşleşmeyi önlemek
    # için Jaccard benzerliği kullanıyoruz.
    return jaccard >= 0.72


def _track_value(track: Any, key: str, default: Any = None) -> Any:
    if track is None:
        return default
    if isinstance(track, Mapping):
        return track.get(key, default)
    if hasattr(track, "get"):
        try:
            return track.get(key, default)
        except TypeError:
            pass
    return getattr(track, key, default)


def track_id(track: Any) -> str:
    value = _track_value(track, "id")
    return str(value) if value is not None else ""


def track_title(track: Any) -> str:
    return str(_track_value(track, "title", "") or "")


def track_artist(track: Any) -> str:
    artist = _clean_artist(_track_value(track, "artist"))
    if artist:
        return artist

    return extract_artist(
        track_title(track),
        uploader=_track_value(track, "uploader") or _track_value(track, "channel"),
    )


def trailing_artist_count(recent_tracks: Sequence[Any], artist: str) -> int:
    """En son çalınan şarkılarda aynı sanatçının kesintisiz tekrar sayısı."""
    if not artist:
        return 0

    count = 0
    for track in reversed(recent_tracks):
        if track_artist(track) == artist:
            count += 1
        else:
            break
    return count


def _append_last_track(source: list[Any], last_track: Any) -> list[Any]:
    if last_track is None:
        return source

    last_id = track_id(last_track)
    if not last_id or not source or track_id(source[-1]) != last_id:
        source.append(last_track)
    return source


@dataclass(frozen=True)
class Candidate:
    """Auto-play için değerlendirilecek aday şarkı."""

    id: str
    title: str
    artist: str = ""
    payload: Any = None

    def __post_init__(self):
        object.__setattr__(self, "id", str(self.id))
        if not self.artist:
            object.__setattr__(self, "artist", extract_artist(self.title))


@dataclass
class SelectionResult:
    candidate: Candidate | None
    blocked: list[tuple[Candidate, list[str]]] = field(default_factory=list)
    relaxed: bool = False
    reason: str | None = None


class AutoplayFilter:
    """Üst üste aynı sanatçıyı ve üst üste aynı şarkıyı engeller."""

    def __init__(self, max_consecutive_artist: int = 2):
        self.max_consecutive_artist = max_consecutive_artist

    def evaluate(
        self,
        candidate: Candidate,
        last_track: Any,
        recent_tracks: Sequence[Any] | None = None,
    ) -> list[str]:
        reasons: list[str] = []
        last_id = track_id(last_track)
        last_title = track_title(last_track)

        if (last_id and candidate.id == last_id) or is_same_song(candidate.title, last_title):
            reasons.append("same_song")

        source = list(recent_tracks or [])
        source = _append_last_track(source, last_track)

        if candidate.artist and trailing_artist_count(source, candidate.artist) >= self.max_consecutive_artist:
            reasons.append("artist_streak")

        return reasons

    def rank(
        self,
        candidates: Iterable[Candidate],
        last_track: Any,
        recent_tracks: Sequence[Any] | None = None,
    ) -> list[Candidate]:
        """Uygun adayları önce, taviz verilen adayları sonra döndürür."""
        strict: list[Candidate] = []
        relaxed: list[Candidate] = []
        fallback: list[Candidate] = []

        for candidate in candidates:
            reasons = self.evaluate(candidate, last_track, recent_tracks)
            if not reasons:
                strict.append(candidate)
            elif "same_song" in reasons:
                fallback.append(candidate)
            else:
                relaxed.append(candidate)

        return strict + relaxed + fallback

    def select(
        self,
        candidates: Iterable[Candidate],
        last_track: Any,
        recent_tracks: Sequence[Any] | None = None,
    ) -> SelectionResult:
        candidates = list(candidates)
        if not candidates:
            return SelectionResult(None)

        blocked: list[tuple[Candidate, list[str]]] = []
        for candidate in candidates:
            reasons = self.evaluate(candidate, last_track, recent_tracks)
            if not reasons:
                return SelectionResult(candidate, blocked, False, None)
            blocked.append((candidate, reasons))

        # Hiç uygun aday yoksa sanatçı sınırını esnet, aynı şarkıyı yine çalma.
        for candidate, reasons in blocked:
            if "same_song" not in reasons:
                return SelectionResult(candidate, blocked, True, "artist_streak_relaxed")

        return SelectionResult(blocked[0][0], blocked, True, "fallback")
