"""Massachusetts location resolution.

Implements README -> "3. Locate". Resolution order, first match wins:

1. Highway (route alias, new exit, old exit, mile marker, route + town)
2. Landmark (MBTA station, campus, named area)
3. Intersection, or street + town
4. Street without a town (single town, nearest-to-device, or ambiguous)
5. Device location only
6. Unknown

Pure function: the reference tables are passed in (defaulting to the loaded
singleton), so tests can supply their own gazetteer.
"""

from __future__ import annotations

from app.contracts import LocationMention, ResolvedLocation
from app.geo import cell_for
from app.reference import ReferenceData, reference_data

#: Confidence levels, named so the thresholds in link/dispatch stay readable.
CONF_EXACT = 0.9
CONF_STREET = 0.8
CONF_MILE = 0.7
CONF_DEVICE = 0.6
CONF_AMBIGUOUS = 0.3

#: Below this, a call is never auto-linked (README -> "4. Link", gates).
MIN_CONFIDENCE_FOR_AUTO_LINK = 0.5

STATE_POLICE = "state-police"

_SUFFIX_DISPLAY = {
    "avenue": "Ave",
    "street": "St",
    "road": "Rd",
    "boulevard": "Blvd",
    "parkway": "Pkwy",
    "square": "Sq",
    "drive": "Dr",
    "lane": "Ln",
    "place": "Pl",
    "terrace": "Ter",
    "court": "Ct",
    "highway": "Hwy",
}


def display_street(canonical: str) -> str:
    """``"massachusetts avenue"`` -> ``"Massachusetts Ave"``."""
    if not canonical:
        return ""
    words = canonical.split()
    out = [_SUFFIX_DISPLAY.get(word, word.title()) for word in words]
    return " ".join(out)


def _located(
    *,
    lat: float,
    lng: float,
    kind: str,
    label: str,
    town: str | None,
    confidence: float,
    agency_hint: str | None = None,
) -> ResolvedLocation:
    return ResolvedLocation(
        lat=lat,
        lng=lng,
        h3=cell_for(lat, lng),
        kind=kind,  # type: ignore[arg-type]
        label=label,
        town=town,
        confidence=confidence,
        ambiguous=False,
        candidates=[],
        agency_hint=agency_hint,
    )


def resolve(
    mention: LocationMention,
    device: tuple[float, float] | None = None,
    reference: ReferenceData | None = None,
) -> ResolvedLocation:
    """Resolve a caller's location words to coordinates.

    Args:
        mention: Location words as extracted, before resolution.
        device: Simulated wireless device location, if the carrier supplied one.
        reference: Lookup tables; defaults to the process-wide reference data.

    Returns:
        A :class:`ResolvedLocation`. ``kind="unknown"`` when nothing matched.
    """
    ref = reference or reference_data()

    for resolver in (
        _resolve_highway,
        _resolve_landmark,
        _resolve_intersection,
        _resolve_street_with_town,
        _resolve_street_without_town,
    ):
        result = resolver(mention, device, ref)
        if result is not None:
            return result

    if device is not None:
        return _resolve_device(mention, device, ref)

    return ResolvedLocation(kind="unknown", label="Unknown location", confidence=0.0)


# ---------------------------------------------------------------------------
# 1. Highway
# ---------------------------------------------------------------------------


def _resolve_highway(
    mention: LocationMention,
    device: tuple[float, float] | None,
    ref: ReferenceData,
) -> ResolvedLocation | None:
    route = ref.highways.canonical_route(mention.highway_route)
    if route is None:
        return None

    direction = ref.highways.canonical_direction(mention.highway_direction)
    town = ref.gazetteer.canonical_town(mention.town)

    entry = None
    confidence = CONF_EXACT

    if mention.highway_exit:
        # New (mile-based) numbering first, then the old sequential numbering.
        # ``exit_is_old`` forces the old table when the caller said "old exit".
        if mention.exit_is_old:
            entry = ref.highways.by_exit(route, mention.highway_exit, old=True)
        else:
            entry = ref.highways.by_exit(route, mention.highway_exit, old=False)
            if entry is None:
                entry = ref.highways.by_exit(route, mention.highway_exit, old=True)

    if entry is None and mention.mile_marker is not None:
        entry = ref.highways.by_mile(route, mention.mile_marker)
        if entry is not None:
            confidence = CONF_MILE

    if entry is None and town:
        entry = ref.highways.by_town(route, town)

    if entry is None:
        # Route named but no exit, mile or town: fall back to the device
        # location while keeping the highway kind, so State Police still route.
        if device is None:
            return None
        return _located(
            lat=device[0],
            lng=device[1],
            kind="highway",
            label=_highway_label(route, direction, None),
            town=town,
            confidence=CONF_DEVICE,
            agency_hint=STATE_POLICE,
        )

    return _located(
        lat=entry.lat,
        lng=entry.lng,
        kind="highway",
        label=_highway_label(route, direction, entry.label()),
        town=entry.town,
        confidence=confidence,
        agency_hint=STATE_POLICE,
    )


def _highway_label(route: str, direction: str | None, detail: str | None) -> str:
    head = f"{route} {direction}" if direction else route
    if detail is None:
        return head
    # ``detail`` already starts with the route name.
    tail = detail[len(route) :].lstrip()
    return f"{head} {tail}".strip()


# ---------------------------------------------------------------------------
# 2. Landmark
# ---------------------------------------------------------------------------


def _resolve_landmark(
    mention: LocationMention,
    device: tuple[float, float] | None,
    ref: ReferenceData,
) -> ResolvedLocation | None:
    # The landmark field is authoritative. The caller's raw location words are
    # scanned only when no street or landmark was extracted, so a phrase such
    # as "he ran toward Hynes" never relocates a call made from the store.
    if mention.landmark:
        texts: tuple[str | None, ...] = (mention.landmark,)
    elif not (mention.street or mention.cross_street):
        texts = (mention.raw,)
    else:
        texts = ()
    entry = ref.landmarks.match(*texts)
    if entry is None:
        return None
    return _located(
        lat=entry.lat,
        lng=entry.lng,
        kind="landmark",
        label=entry.name,
        town=entry.town,
        confidence=CONF_EXACT,
        agency_hint=entry.agency_hint,
    )


# ---------------------------------------------------------------------------
# 3. Intersection / street + town
# ---------------------------------------------------------------------------


def _resolve_intersection(
    mention: LocationMention,
    device: tuple[float, float] | None,
    ref: ReferenceData,
) -> ResolvedLocation | None:
    gazetteer = ref.gazetteer
    entry = gazetteer.intersection(mention.street, mention.cross_street, mention.town)
    if entry is None and mention.town:
        # Town named but not matching: retry without the town constraint.
        entry = gazetteer.intersection(mention.street, mention.cross_street)
    if entry is None:
        entry = gazetteer.intersection(mention.street, mention.cross_street, None)
    if entry is None:
        return None

    label = (
        f"{display_street(entry.street)} & {display_street(entry.cross_street)}, {entry.town}"
    )
    return _located(
        lat=entry.lat,
        lng=entry.lng,
        kind="intersection",
        label=label,
        town=entry.town,
        confidence=CONF_EXACT,
    )


def _resolve_street_with_town(
    mention: LocationMention,
    device: tuple[float, float] | None,
    ref: ReferenceData,
) -> ResolvedLocation | None:
    entry = ref.gazetteer.street_in_town(mention.street, mention.town)
    if entry is None:
        return None
    return _located(
        lat=entry.lat,
        lng=entry.lng,
        kind="street",
        label=f"{display_street(entry.name)}, {entry.town}",
        town=entry.town,
        confidence=CONF_STREET,
    )


# ---------------------------------------------------------------------------
# 4. Street without a town
# ---------------------------------------------------------------------------


def _resolve_street_without_town(
    mention: LocationMention,
    device: tuple[float, float] | None,
    ref: ReferenceData,
) -> ResolvedLocation | None:
    gazetteer = ref.gazetteer
    matches = gazetteer.streets_named(mention.street)
    if not matches:
        return None

    if len(matches) == 1:
        entry = matches[0]
        return _located(
            lat=entry.lat,
            lng=entry.lng,
            kind="street",
            label=f"{display_street(entry.name)}, {entry.town}",
            town=entry.town,
            confidence=CONF_STREET,
        )

    if device is not None:
        entry = gazetteer.nearest_street_entry(mention.street, device)
        if entry is not None:
            return _located(
                lat=entry.lat,
                lng=entry.lng,
                kind="street",
                label=f"{display_street(entry.name)}, {entry.town}",
                town=entry.town,
                confidence=CONF_STREET,
            )

    # Several towns share this street and there is no device location. Keep the
    # call, flag it ambiguous, and let the operator ask which town.
    street_name = display_street(gazetteer.canonical_street(mention.street))
    return ResolvedLocation(
        lat=None,
        lng=None,
        h3=None,
        kind="street",
        label=street_name,
        town=None,
        confidence=CONF_AMBIGUOUS,
        ambiguous=True,
        candidates=[entry.town for entry in matches],
    )


# ---------------------------------------------------------------------------
# 5. Device only
# ---------------------------------------------------------------------------


def _resolve_device(
    mention: LocationMention,
    device: tuple[float, float],
    ref: ReferenceData,
) -> ResolvedLocation:
    lat, lng = device
    nearby = ref.landmarks.near(device, radius_m=250)
    town = ref.gazetteer.canonical_town(mention.town) or (nearby.town if nearby else None)
    label = f"Device location near {nearby.name}" if nearby else f"Device location {lat:.4f}, {lng:.4f}"
    return _located(
        lat=lat,
        lng=lng,
        kind="device",
        label=label,
        town=town,
        confidence=CONF_DEVICE,
        agency_hint=nearby.agency_hint if nearby else None,
    )


def candidate_street_names(location: ResolvedLocation, ref: ReferenceData | None = None) -> list[str]:
    """Canonical street name behind an ambiguous location, for candidate search."""
    reference_tables = ref or reference_data()
    return [reference_tables.gazetteer.canonical_street(location.label)] if location.ambiguous else []
