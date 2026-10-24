"""Massachusetts reference data: gazetteer, highways, landmarks, agencies, rules.

Loaded once per process and exposed as immutable, typed lookup tables. No
pipeline module reads a JSON file or knows a path; they all ask this module.

All coordinates are approximate and demo-only (README -> "Demo anchor
coordinates"). Production would source MassGIS and MassDOT.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.geo import haversine_m, nearest
from app.paths import (
    AGENCIES_FILE,
    DISPATCH_RULES_FILE,
    GAZETTEER_FILE,
    HIGHWAYS_FILE,
    LANDMARKS_FILE,
)
from app.text import normalize

# ---------------------------------------------------------------------------
# Row types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StreetEntry:
    name: str
    town: str
    lat: float
    lng: float

    @property
    def coords(self) -> tuple[float, float]:
        return (self.lat, self.lng)


@dataclass(frozen=True, slots=True)
class IntersectionEntry:
    street: str
    cross_street: str
    town: str
    lat: float
    lng: float

    @property
    def coords(self) -> tuple[float, float]:
        return (self.lat, self.lng)


@dataclass(frozen=True, slots=True)
class ExitEntry:
    route: str
    new_exit: str
    old_exit: str
    mile: float
    town: str
    lat: float
    lng: float

    @property
    def coords(self) -> tuple[float, float]:
        return (self.lat, self.lng)

    def label(self) -> str:
        return f"{self.route} Exit {self.new_exit} (old Exit {self.old_exit}), {self.town}"


@dataclass(frozen=True, slots=True)
class LandmarkEntry:
    id: str
    name: str
    kind: str
    town: str | None
    lat: float
    lng: float
    agency_hint: str | None
    aliases: tuple[str, ...]

    @property
    def coords(self) -> tuple[float, float]:
        return (self.lat, self.lng)


@dataclass(frozen=True, slots=True)
class AgencyEntry:
    id: str
    name: str
    kind: str
    town: str | None


@dataclass(frozen=True, slots=True)
class DispatchRule:
    id: str
    types: tuple[str, ...]
    requires_flags: tuple[str, ...]
    location_kinds: tuple[str, ...]
    units: tuple[str, ...]

    def matches(self, incident_type: str, flags: dict[str, bool], location_kind: str) -> bool:
        if self.types and incident_type not in self.types:
            return False
        if self.location_kinds and location_kind not in self.location_kinds:
            return False
        return all(flags.get(flag, False) for flag in self.requires_flags)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Gazetteer:
    """Street and intersection lookups with Massachusetts naming quirks."""

    def __init__(
        self,
        streets: list[StreetEntry],
        intersections: list[IntersectionEntry],
        phrase_aliases: dict[str, str],
        suffix_aliases: dict[str, str],
        town_aliases: dict[str, str],
    ) -> None:
        self._streets = tuple(streets)
        self._intersections = tuple(intersections)
        self._suffix_aliases = dict(suffix_aliases)
        self._town_aliases = dict(town_aliases)
        # Longest phrase first so "massachusetts ave" wins over "mass ave".
        self._phrase_aliases = tuple(
            sorted(phrase_aliases.items(), key=lambda kv: len(kv[0]), reverse=True)
        )

        by_name: dict[str, list[StreetEntry]] = {}
        for entry in self._streets:
            by_name.setdefault(entry.name, []).append(entry)
        self._by_name = {name: tuple(entries) for name, entries in by_name.items()}

    # -- normalization ------------------------------------------------------

    def canonical_street(self, raw: str | None) -> str:
        """Canonical street name: ``"Mass Ave"`` -> ``"massachusetts avenue"``."""
        if not raw:
            return ""
        name = normalize(raw)
        if not name:
            return ""
        for phrase, replacement in self._phrase_aliases:
            if phrase in name:
                name = name.replace(phrase, replacement)
        expanded = [self._suffix_aliases.get(token, token) for token in name.split()]
        return " ".join(expanded)

    def canonical_town(self, raw: str | None) -> str | None:
        """Canonical town name, or None when ``raw`` is empty/unknown."""
        if not raw:
            return None
        key = normalize(raw)
        if not key:
            return None
        if key in self._town_aliases:
            return self._town_aliases[key]
        return key.title()

    # -- lookups ------------------------------------------------------------

    def streets_named(self, street: str | None) -> tuple[StreetEntry, ...]:
        """Every town that has a street by this name."""
        return self._by_name.get(self.canonical_street(street), ())

    def street_in_town(self, street: str | None, town: str | None) -> StreetEntry | None:
        canonical_town = self.canonical_town(town)
        if canonical_town is None:
            return None
        for entry in self.streets_named(street):
            if entry.town == canonical_town:
                return entry
        return None

    def towns_for_street(self, street: str | None) -> list[str]:
        return [entry.town for entry in self.streets_named(street)]

    def intersection(
        self,
        street: str | None,
        cross_street: str | None,
        town: str | None = None,
    ) -> IntersectionEntry | None:
        """Find an intersection, trying both street orders."""
        a = self.canonical_street(street)
        b = self.canonical_street(cross_street)
        if not a or not b:
            return None
        canonical_town = self.canonical_town(town)
        for entry in self._intersections:
            if canonical_town is not None and entry.town != canonical_town:
                continue
            if {entry.street, entry.cross_street} == {a, b}:
                return entry
        return None

    def nearest_street_entry(
        self,
        street: str | None,
        point: tuple[float, float],
    ) -> StreetEntry | None:
        """Among towns sharing a street name, the candidate nearest ``point``."""
        candidates = self.streets_named(street)
        if not candidates:
            return None
        index = nearest(point, [entry.coords for entry in candidates])
        return candidates[index] if index is not None else None


class HighwayTable:
    """Route aliases plus the old/new exit cross-reference."""

    def __init__(
        self,
        exits: list[ExitEntry],
        route_aliases: dict[str, str],
        direction_aliases: dict[str, str],
    ) -> None:
        self._exits = tuple(exits)
        self._route_aliases = dict(route_aliases)
        self._direction_aliases = dict(direction_aliases)

    def canonical_route(self, raw: str | None) -> str | None:
        """``"the Pike"`` / ``"90"`` -> ``"I-90"``."""
        if not raw:
            return None
        key = normalize(raw)
        if not key:
            return None
        if key in self._route_aliases:
            return self._route_aliases[key]
        # Tolerate extra words such as "the mass pike eastbound".
        for alias, route in sorted(
            self._route_aliases.items(), key=lambda kv: len(kv[0]), reverse=True
        ):
            if alias in key.split() or alias in key:
                return route
        upper = raw.strip().upper().replace(" ", "-")
        return upper if upper.startswith("I-") else None

    def canonical_direction(self, raw: str | None) -> str | None:
        if not raw:
            return None
        return self._direction_aliases.get(normalize(raw))

    def by_exit(self, route: str, exit_number: str, old: bool) -> ExitEntry | None:
        """Look up an exit by its old or new number."""
        wanted = normalize(exit_number)
        if not wanted:
            return None
        for entry in self._exits:
            if entry.route != route:
                continue
            candidate = entry.old_exit if old else entry.new_exit
            if normalize(candidate) == wanted:
                return entry
        return None

    def by_mile(self, route: str, mile: float) -> ExitEntry | None:
        """Nearest exit on ``route`` to a mile marker."""
        on_route = [entry for entry in self._exits if entry.route == route]
        if not on_route:
            return None
        return min(on_route, key=lambda entry: abs(entry.mile - mile))

    def by_town(self, route: str, town: str | None) -> ExitEntry | None:
        if not town:
            return None
        for entry in self._exits:
            if entry.route == route and entry.town == town:
                return entry
        return None


class LandmarkTable:
    """Alias-matched MBTA stations, campuses and named areas."""

    def __init__(self, landmarks: list[LandmarkEntry]) -> None:
        self._landmarks = tuple(landmarks)
        index: list[tuple[str, LandmarkEntry]] = []
        for entry in self._landmarks:
            for alias in (*entry.aliases, entry.name):
                normalized = normalize(alias)
                if normalized:
                    index.append((normalized, entry))
        # Longest alias first, so "hynes convention center" beats "hynes".
        self._index = tuple(sorted(index, key=lambda pair: len(pair[0]), reverse=True))

    def match(self, *texts: str | None) -> LandmarkEntry | None:
        """First landmark whose alias appears in any of ``texts``."""
        haystacks = [normalize(text) for text in texts if text]
        haystacks = [h for h in haystacks if h]
        if not haystacks:
            return None
        for alias, entry in self._index:
            for haystack in haystacks:
                if alias == haystack or alias in haystack:
                    return entry
        return None

    def near(self, point: tuple[float, float], radius_m: float) -> LandmarkEntry | None:
        """Closest landmark within ``radius_m``, if any."""
        within = [e for e in self._landmarks if haversine_m(point, e.coords) <= radius_m]
        if not within:
            return None
        return min(within, key=lambda e: haversine_m(point, e.coords))


class AgencyTable:
    """Agency directory with town and kind lookups."""

    def __init__(self, agencies: list[AgencyEntry]) -> None:
        self._agencies = tuple(agencies)
        self._by_id = {entry.id: entry for entry in self._agencies}

    def get(self, agency_id: str | None) -> AgencyEntry | None:
        return self._by_id.get(agency_id) if agency_id else None

    def name_of(self, agency_id: str | None) -> str | None:
        entry = self.get(agency_id)
        return entry.name if entry else None

    def by_kind_and_town(self, kind: str, town: str | None) -> AgencyEntry | None:
        """Agency of ``kind`` serving ``town``, else the generic one."""
        if town:
            for entry in self._agencies:
                if entry.kind == kind and entry.town == town:
                    return entry
        for entry in self._agencies:
            if entry.kind == kind and entry.town is None:
                return entry
        return None

    def police_for_town(self, town: str | None) -> AgencyEntry | None:
        return self.by_kind_and_town("local_pd", town)

    def fire_for_town(self, town: str | None) -> AgencyEntry | None:
        return self.by_kind_and_town("fire", town)

    def ems_for_town(self, town: str | None) -> AgencyEntry | None:
        return self.by_kind_and_town("ems", town)


class DispatchRuleSet:
    """Ordered, first-match-wins unit recommendations. Illustrative only."""

    def __init__(self, rules: list[DispatchRule]) -> None:
        self._rules = tuple(rules)

    def first_match(
        self,
        incident_type: str,
        flags: dict[str, bool],
        location_kind: str,
    ) -> DispatchRule:
        for rule in self._rules:
            if rule.matches(incident_type, flags, location_kind):
                return rule
        return DispatchRule(
            id="default", types=(), requires_flags=(), location_kinds=(), units=("1 Police",)
        )


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceData:
    """Every static lookup table, loaded once."""

    gazetteer: Gazetteer
    highways: HighwayTable
    landmarks: LandmarkTable
    agencies: AgencyTable
    dispatch_rules: DispatchRuleSet
    _sources: tuple[Path, ...] = field(default=())


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Reference data file missing: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Reference data file must hold a JSON object: {path}")
    return payload


def _load_gazetteer(payload: dict[str, Any], gaz_streets: list[StreetEntry]) -> Gazetteer:
    intersections = [
        IntersectionEntry(
            street=normalize(row["street"]),
            cross_street=normalize(row["cross_street"]),
            town=row["town"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
        )
        for row in payload.get("intersections", [])
    ]
    return Gazetteer(
        streets=gaz_streets,
        intersections=intersections,
        phrase_aliases=payload.get("phrase_aliases", {}),
        suffix_aliases=payload.get("suffix_aliases", {}),
        town_aliases=payload.get("town_aliases", {}),
    )


@lru_cache(maxsize=1)
def reference_data() -> ReferenceData:
    """Load and cache every reference table."""
    gazetteer_payload = _read_json(GAZETTEER_FILE)
    streets = [
        StreetEntry(
            name=normalize(row["name"]),
            town=row["town"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
        )
        for row in gazetteer_payload.get("streets", [])
    ]

    highways_payload = _read_json(HIGHWAYS_FILE)
    exits = [
        ExitEntry(
            route=row["route"],
            new_exit=str(row["new_exit"]),
            old_exit=str(row["old_exit"]),
            mile=float(row["mile"]),
            town=row["town"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
        )
        for row in highways_payload.get("exits", [])
    ]

    landmarks_payload = _read_json(LANDMARKS_FILE)
    landmarks = [
        LandmarkEntry(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            town=row.get("town"),
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            agency_hint=row.get("agency_hint"),
            aliases=tuple(row.get("aliases", ())),
        )
        for row in landmarks_payload.get("landmarks", [])
    ]

    agencies_payload = _read_json(AGENCIES_FILE)
    agencies = [
        AgencyEntry(
            id=row["id"], name=row["name"], kind=row["kind"], town=row.get("town")
        )
        for row in agencies_payload.get("agencies", [])
    ]

    rules_payload = _read_json(DISPATCH_RULES_FILE)
    rules = [
        DispatchRule(
            id=row["id"],
            types=tuple(row.get("types", ())),
            requires_flags=tuple(row.get("requires_flags", ())),
            location_kinds=tuple(row.get("location_kinds", ())),
            units=tuple(row.get("units", ())),
        )
        for row in rules_payload.get("rules", [])
    ]

    return ReferenceData(
        gazetteer=_load_gazetteer(gazetteer_payload, streets),
        highways=HighwayTable(
            exits=exits,
            route_aliases=highways_payload.get("route_aliases", {}),
            direction_aliases=highways_payload.get("direction_aliases", {}),
        ),
        landmarks=LandmarkTable(landmarks),
        agencies=AgencyTable(agencies),
        dispatch_rules=DispatchRuleSet(rules),
        _sources=(GAZETTEER_FILE, HIGHWAYS_FILE, LANDMARKS_FILE, AGENCIES_FILE, DISPATCH_RULES_FILE),
    )


def clear_reference_cache() -> None:
    """Drop the cached tables. For tests that rewrite the data files."""
    reference_data.cache_clear()
