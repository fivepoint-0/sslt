SHELL := /usr/bin/env bash

.PHONY: test release screenshots

test:
	uv run pytest

release: screenshots
	@if [[ -z "$(VERSION)" ]]; then \
		echo "Usage: make release VERSION=0.1.0"; \
		exit 1; \
	fi
	@bash scripts/release.sh "$(VERSION)"

screenshots:
	uv run python scripts/generate_docs_screenshots.py
