# Model cards for Starscream-trained models

If you train a model on Starscream export data, you must publish a model card that credits the corpus and downstream contributors. This satisfies the [AI training attribution clause](./GOVERNANCE.md#ai-training-attribution-clause).

## Quick start

After exporting a dataset:

```bash
starscream-export run ./dataset/ --format jsonl

starscream-model-card generate \
  --export-dir ./dataset/ \
  --model-name my-audio-world-model \
  --output MODEL_CARD.md
```

The tool reads:

- `export_meta.json` — totals, splits, formats, audio download count
- `dataset.jsonl` (or `train.jsonl` + `val.jsonl`) — contributor counts and license breakdown

It writes a Markdown model card with citation blocks ready for Hugging Face or a paper supplement.

## What to include

Every model card should contain:

| Section | Content |
|---|---|
| **Training data** | Export path, recording counts, split policy, contributor count |
| **License breakdown** | CC0 vs CC-BY counts from the export used |
| **Attribution** | Credit to Starscream Foundation + individual `contributor_id` values |
| **Citation** | Plain-text and BibTeX referencing `https://data.starscream.org` |
| **Governance** | Statement that the card fulfills the Starscream AI training clause |

## Citation template

**Plain text:**

> Starscream Foundation and Contributors. Starscream Open Acoustic Corpus. https://data.starscream.org. Used to train *your-model-name*.

**BibTeX:**

```bibtex
@misc{starscream_corpus,
  title        = {Starscream Open Acoustic Corpus},
  author       = {Starscream Foundation and Contributors},
  year         = {2024},
  howpublished = {\url{https://data.starscream.org}},
  note         = {Training data for model YOUR-MODEL-NAME}
}
```

Replace `YOUR-MODEL-NAME` with your published model identifier.

## Contributor attribution

Export rows include:

- `contributor_id` — stable identifier for voting weight and attribution
- `contributor_name` — display name (optional)

When reporting benchmark results or publishing weights, cite the Starscream corpus **and** note that individual contributors are listed in the export metadata. Do not strip contributor fields from derived datasets without foundation approval.

## Hugging Face Hub

1. Run `starscream-model-card generate` into your model repo root as `MODEL_CARD.md` (or merge into `README.md`).
2. Set the model card license to match your **weights** license (dataset rows remain CC0/CC-BY).
3. Add tags: `starscream`, `audio`, `world-models`.
4. Link to the exact export snapshot or Hugging Face dataset repo if you republished the corpus.

## Policy reference

- Full governance: [GOVERNANCE.md](./GOVERNANCE.md)
- JSON policy summary: `GET /v1/governance`
- Export layout: [EXPORT.md](./EXPORT.md)
