# Build and check the documentation portal. Details: tools/site/README.md.
#
#   make docs-deps    install the pinned build dependencies, fetch the vendored Mermaid
#   make docs-check   check the Markdown sources (no build needed)
#   make docs-build   unit tests, strict build into site/, checks on the built site
#   make docs-test    unit tests of tools/site only
#   make docs-serve   live preview on http://localhost:8000
#   make docs-clean   remove what the build generates
#
# Python: `python3` from PATH by default, which is what CI uses. When the
# virtual environment .venv exists it is used instead, without activation:
#
#   python3 -m venv .venv
#   make docs-deps
#   make docs-check docs-build
#
# Variables: PYTHON=<interpreter> forces an interpreter, STRICT=1 reports the
# warnings of the checks as errors, DEV_ADDR=<ip:port> moves the preview.

VENV ?= .venv
ifneq ($(wildcard $(VENV)/bin/python),)
PYTHON ?= $(VENV)/bin/python
else
PYTHON ?= python3
endif

# Must match `site_dir` in zensical.toml.
SITE_DIR := site
DEV_ADDR ?= localhost:8000
STRICT ?=
CHECK_FLAGS := $(if $(filter-out 0,$(STRICT)),--strict)

# tools/site holds the local Markdown extension (portal_mdx) that
# zensical.toml enables: Zensical and the unit tests must be able to import it.
SITE_ENV := PYTHONPATH="$(CURDIR)/tools/site$(if $(PYTHONPATH),:$(PYTHONPATH))"
ZENSICAL := $(SITE_ENV) $(PYTHON) -m zensical

.DEFAULT_GOAL := help
.PHONY: help docs-deps docs-check docs-test docs-build docs-serve docs-clean

help:
	@echo "make docs-deps    install the pinned build dependencies, fetch the vendored Mermaid"
	@echo "make docs-check   check the Markdown sources (no build needed)"
	@echo "make docs-build   unit tests, strict build into $(SITE_DIR)/, checks on the built site"
	@echo "make docs-test    unit tests of tools/site only"
	@echo "make docs-serve   live preview on http://$(DEV_ADDR)"
	@echo "make docs-clean   remove what the build generates"
	@echo "Python: $(PYTHON)   (STRICT=1: warnings of the checks are errors)"

# The only target that needs the network: PyPI, then the pinned Mermaid bundle
# (not committed; fetch_vendor.py verifies its checksum).
docs-deps:
	$(PYTHON) -m pip install -r requirements-docs.txt
	$(PYTHON) tools/site/fetch_vendor.py

docs-check:
	$(PYTHON) tools/site/check_docs.py $(CHECK_FLAGS)

docs-test:
ifneq ($(wildcard tools/site/tests),)
	$(SITE_ENV) $(PYTHON) -m unittest discover -s tools/site/tests
else
	@echo "docs-test: no tools/site/tests directory, nothing to run"
endif

# --strict: any warning of Zensical (broken link or anchor, ...) fails the build.
docs-build: docs-test
	$(PYTHON) tools/site/prebuild.py
	$(ZENSICAL) build --clean --strict
	$(PYTHON) tools/site/check_site.py $(SITE_DIR) $(CHECK_FLAGS)

docs-serve:
	$(PYTHON) tools/site/prebuild.py
	$(ZENSICAL) serve --dev-addr $(DEV_ADDR)

# The downloaded Mermaid bundle is a dependency, not a build product: it stays.
docs-clean:
	rm -rf $(SITE_DIR) .cache docs/assets/data/updates.json
	find tools -type d -name __pycache__ -prune -exec rm -rf {} +
