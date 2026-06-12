# Starscream Foundation Governance

Starscream is infrastructure, not a product. Governance keeps the acoustic corpus open, attributable, and collectively stewarded.

## License policy

All **contributed** recordings must use one of:

- **CC0** — public domain dedication
- **CC-BY** — attribution required

The following are **not** accepted for contributed uploads:

- **NC** (non-commercial) — blocks research and model training use
- **ND** (no derivatives) — blocks dataset exports and derived works

**Federated archives:** recordings under non-CC licenses are ingested by **pointer only** (metadata + link to the upstream archive). Starscream does not redistribute restricted audio.

## Foundation

The **Starscream Foundation** is a nonprofit steward of the catalog and export infrastructure.

- **Board election:** held annually
- **Voter weighting:** proportional to verified contribution volume (recordings, sensor uptime, federation connectors, mirrors)
- **Control:** no single organization may hold a controlling stake in dataset policy or infrastructure decisions

## Dispute resolution

Disputes follow a Wikipedia-style process:

1. **Flag** — any contributor or reviewer flags a recording, metadata error, or policy concern
2. **Discuss** — thread on the recording talk page or `discuss.starscream.org`
3. **Escalate** — unresolved cases go to the **arbitration committee**

**Vandalism** (fake GPS, fabricated audio, license misrepresentation) is flagged automatically where possible and reviewed by the **moderator council**. Confirmed vandalism results in record quarantine and contributor sanctions.

## Mirror reciprocity

Organizations that mirror **more than 10 TB** of Starscream object storage must provide a **public seed** (BitTorrent or equivalent) so others can replicate without exclusive bandwidth costs.

This is **infrastructure reciprocity**: bulk consumers help distribute the corpus they depend on. See [STORAGE.md](./STORAGE.md) for mirror and torrent tooling.

## AI training attribution clause

Any model trained on Starscream export data must:

1. Publish a **model card** crediting the Starscream corpus
2. Link to `https://data.starscream.org` (or the export snapshot used)
3. Preserve **contributor attribution** via `contributor_id` / `contributor_name` fields in training metadata and published documentation

Generate a compliant card with:

```bash
starscream-model-card generate \
  --export-dir ./dataset/ \
  --model-name my-model \
  --output MODEL_CARD.md
```

See [MODEL_CARD.md](./MODEL_CARD.md) for citation templates and Hugging Face publishing guidance.

## API

Policy summaries are available programmatically:

```
GET /v1/governance
```

## Participation

Ways to engage with governance:

- Contribute verified recordings (earns voting weight)
- Join foundation working groups on policy drafts
- Operate regional mirrors and public seeds
- Report disputes and quality issues through the flag workflow
