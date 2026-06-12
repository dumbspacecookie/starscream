"""Spectral-hash deduplication — link duplicates, prefer higher-quality audio."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.db.models import Recording

QUALITY_FLAC = 3
QUALITY_MP3 = 2
QUALITY_POINTER = 1
QUALITY_NONE = 0


def audio_quality_tier(recording: Recording) -> int:
    """Rank audio storage: flac > mp3 > pointer-only."""
    if recording.flac_key:
        return QUALITY_FLAC
    if recording.mp3_key:
        return QUALITY_MP3
    if recording.external_url or recording.external_id:
        return QUALITY_POINTER
    return QUALITY_NONE


def resolve_canonical(recording: Recording) -> Recording:
    """Return the canonical recording (self when not a duplicate)."""
    current = recording
    seen = {current.id}
    while current.canonical_id is not None:
        if current.canonical_id in seen:
            return current
        parent = current.canonical
        if parent is None:
            return current
        if parent.id in seen:
            return parent
        seen.add(parent.id)
        current = parent
    return current


def find_duplicate(db: Session, spectral_hash: str) -> Recording | None:
    """Find an existing recording with the same spectral hash, if any."""
    match = db.execute(
        select(Recording).where(Recording.spectral_hash == spectral_hash).limit(1)
    ).scalar_one_or_none()
    if match is None:
        return None
    return resolve_canonical(match)


def _promote_audio(canonical: Recording, source: Recording) -> None:
    """Copy higher-quality audio pointers from source onto canonical."""
    if audio_quality_tier(source) <= audio_quality_tier(canonical):
        return
    if source.flac_key:
        canonical.flac_key = source.flac_key
    if source.mp3_key and not canonical.flac_key:
        canonical.mp3_key = source.mp3_key
    if source.duration_s and not canonical.duration_s:
        canonical.duration_s = source.duration_s


def link_duplicate(db: Session, new_recording: Recording, canonical: Recording) -> Recording:
    """Mark new_recording as duplicate of canonical; promote audio if better."""
    canonical = resolve_canonical(canonical)
    new_recording.canonical_id = canonical.id
    new_recording.is_duplicate = True
    _promote_audio(canonical, new_recording)
    return new_recording


def _canonical_rank(recording: Recording) -> tuple[int, int]:
    """Sort key: higher audio tier wins; UUID int breaks ties stably."""
    return (audio_quality_tier(recording), recording.id.int)


def link_cross_source_duplicates(db: Session, recording: Recording) -> Recording:
    """Find same-hash recordings from other sources and unify the canonical chain."""
    peers = list(
        db.scalars(
            select(Recording).where(
                Recording.spectral_hash == recording.spectral_hash,
                Recording.source_id != recording.source_id,
            )
        ).all()
    )
    if not peers:
        return resolve_canonical(recording)

    members: list[Recording] = []
    seen: set = set()
    for rec in (recording, *peers):
        if rec.id in seen:
            continue
        seen.add(rec.id)
        members.append(rec)

    roots = {resolve_canonical(m).id: resolve_canonical(m) for m in members}
    canonical = max(roots.values(), key=_canonical_rank)

    for member in members:
        if member.id != canonical.id:
            link_duplicate(db, member, canonical)

    return resolve_canonical(recording)


def get_canonical_chain(db: Session, recording: Recording) -> tuple[Recording, list[Recording]]:
    """Return the canonical recording and all direct alternates in its chain."""
    canonical = resolve_canonical(recording)
    alternates = list(
        db.scalars(
            select(Recording).where(
                Recording.canonical_id == canonical.id,
                Recording.id != canonical.id,
            )
        ).all()
    )
    return canonical, alternates
