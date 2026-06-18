# Goshinsho 1.2.0

Released: 2026-06-17

## Summary

- Rebuilt and installed clean Portuguese and Japanese E5-large indexes.
- Restored translation handling for pasted teachings in chat.
- Improved language selection behavior on web, mobile, and Android WebView.
- Added interface translation for Portuguese, English, Spanish, and French, with English fallback for other UI languages.
- Fixed the free account entry point from the landing/app quota area.
- Added conservative cleanup rules and preserved reconstruction artifacts after the file-loss incident.
- Replaced the legacy extracted collection with `data/publication_sources`, organized by publication source and date.

## Indexes

- Model: `intfloat/multilingual-e5-large`
- Portuguese chunks: `7100`
- Japanese chunks: `3140`

## Collection Export

- Directory: `data/publication_sources`
- Archive: `/var/backups/goshinsho/trash/20260618T012650Z-project-cleanup/exports/publication_sources_clean_20260617.tar.gz`

