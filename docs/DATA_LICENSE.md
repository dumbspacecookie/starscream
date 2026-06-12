# Data license

## Posture: catalog, not host

Starscream’s default is **metadata + upstream links**, not re-hosting audio. See [REDISTRIBUTION.md](./REDISTRIBUTION.md) for what may live in git vs what must stay at source.

## Contributed recordings

Audio and metadata submitted by contributors to Starscream must use **CC0** or **CC-BY** only (enforced at upload validation). Contributors retain authorship; Starscream catalogs and redistributes under the declared license.

Recommended default: **CC0 1.0 Universal** — maximally open for ML training and research.

## Federated / harvested archives

Each source retains its upstream license (Freesound CC-BY, Xeno-canto CC-BY-NC, Internet Archive public domain, etc.). Starscream stores `license` per recording and surfaces it in export and API responses.

**CC-BY-NC and unclear licenses:** pointer-only (metadata + `external_url`); no local audio copy.

## NOAA / NASA seed catalogs

Bundled metadata pointers reference U.S. government public-domain media. Audio is fetched from upstream URLs; license is recorded as public domain per source policy.

## Code

The Starscream software is licensed under the MIT License — see [LICENSE](../LICENSE) in the repository root.
