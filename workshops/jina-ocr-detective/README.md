# jina-ocr-detective: delivery bundle

The runtime bundle for the Instruqt workshop "Document Detective: Chase a Thief with Jina OCR" (track source: `elastic/instruqt-field-tracks-dev`, `tracks/jina-ocr-detective/`).

- `detective-bundle.tar.gz`: the app (FastAPI and a prebuilt frontend), `detective_core`, the precomputed fictional evidence corpus (pages, OCR markdown, image vectors) and the Brief slides. The challenge setup scripts download it at a pinned commit and verify `detective-bundle.sha256`.
- All documents, people, companies and images in the corpus are fictional; images were AI-generated (Gemini 3 Pro Image). Answers are stored hashed only.
- Do not edit by hand. Rebuild with `tracks/jina-ocr-detective/scripts/make_bundle.sh` and re-pin with `scripts/set_assets_sha.sh`.
