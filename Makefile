.DEFAULT_GOAL := help

.PHONY: install
install:  ## Install all dev dependencies
	uv sync --group dev

.PHONY: help
help:  ## Show this help
	@echo "[Help] Makefile list commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: showoutdated
showoutdated:  ## Show outdated dependencies (Python, prek)
	uv tree --all-groups --outdated | grep --color=always "(latest:.*)" || true
	uv run prek auto-update --dry-run

.PHONY: test
test:  ## Run tests with coverage
	uv run coverage run manage.py test tests --buffer --durations 10 --noinput --parallel --shuffle --timing
	uv run coverage combine
	uv run coverage html
	uv run coverage report

.PHONY: update
update:  ## Update dependencies, pre-commit hooks and GitHub Actions versions
	uv lock --upgrade
	uv sync --group dev
	uv run prek autoupdate
	gha-update

.PHONY: validate
validate:  ## Run pre-commit hooks on all files
	uv run prek run --all-files

.PHONY: publish
publish:  ## Tag current version and push to trigger PyPI publish via GitHub CI
	$(eval VERSION := $(shell grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2))
	git tag v$(VERSION)
	git push origin v$(VERSION)
