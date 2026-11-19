# Build and check the documentation portal. Details: tools/site/README.md.
#
# The portal is one site per release of versions.toml, published under its own
# URL prefix (site/<id>/), plus the root of the portal (landing page,
# not-found page, versions.json, one page per planned release).
#
#   make docs-deps      install the pinned build dependencies, fetch the vendored Mermaid
#   make docs-check     check the Markdown sources (no build needed)
#   make docs-build     unit tests, strict build into site/, checks on the built portal
#   make docs-test      unit tests of tools/site only
#   make docs-serve     live preview of one release, rebuilt on change
#   make docs-preview   serve the built portal as GitHub Pages publishes it
#   make docs-clean     remove what the build generates
#
# Python: `python3` from PATH by default, which is what CI uses. When the
# virtual environment .venv exists it is used instead, without activation:
#
#   python3 -m venv .venv
#   make docs-deps
#   make docs-check docs-build
#
# Variables:
#   RELEASE=<id>        docs-check, docs-build: that release only (docs-build
#                       also rebuilds the root); docs-serve: the release to
#                       preview (default: the default release of versions.toml)
#   STRICT=1            the warnings of the checks are errors (CI runs
#                       docs-check and docs-build with STRICT=1)
#   PYTHON=<interpreter>
#   DEV_ADDR=<ip:port>  address of docs-serve and docs-preview

VENV ?= .venv
ifneq ($(wildcard $(VENV)/bin/python),)
PYTHON ?= $(VENV)/bin/python
else
PYTHON ?= python3
endif

# Must match SITE_DIR in tools/site/releases.py.
SITE_DIR := site
DEV_ADDR ?= localhost:8000
STRICT ?=
RELEASE ?=
CHECK_FLAGS := $(if $(filter-out 0,$(STRICT)),--strict)
RELEASE_FLAG := $(if $(RELEASE),--release $(RELEASE))

# tools/site holds the local Markdown extension (portal_mdx) that
# zensical.base.toml enables: the unit tests must be able to import it
# (build.py sets the same path for Zensical).
SITE_ENV := PYTHONPATH="$(CURDIR)/tools/site$(if $(PYTHONPATH),:$(PYTHONPATH))"

.DEFAULT_GOAL := help
.PHONY: help docs-deps docs-check docs-test docs-build docs-serve docs-preview docs-clean

help:
	@echo "make docs-deps      install the pinned build dependencies, fetch the vendored Mermaid"
	@echo "make docs-check     check the Markdown sources (no build needed)"
	@echo "make docs-build     unit tests, strict build into $(SITE_DIR)/, checks on the built portal"
	@echo "make docs-test      unit tests of tools/site only"
	@echo "make docs-serve     live preview of one release on http://$(DEV_ADDR)"
	@echo "make docs-preview   serve the built portal on http://$(DEV_ADDR), as GitHub Pages publishes it"
	@echo "make docs-clean     remove what the build generates"
	@echo "Python: $(PYTHON)   (RELEASE=<id>: one release; STRICT=1: warnings of the checks are errors)"
	@echo "Available releases: $$($(PYTHON) tools/site/releases.py list --status available | tr '\n' ' ')"
	@echo "Planned releases:   $$($(PYTHON) tools/site/releases.py list --status planned | tr '\n' ' ')"

# The only target that needs the network: PyPI, then the pinned Mermaid bundle
# (not committed; fetch_vendor.py verifies its checksum).
docs-deps:
	$(PYTHON) -m pip install -r requirements-docs.txt
	$(PYTHON) tools/site/fetch_vendor.py

docs-check:
	$(PYTHON) tools/site/check_docs.py $(CHECK_FLAGS) $(RELEASE_FLAG)
	$(PYTHON) tools/site/check_learning.py $(CHECK_FLAGS) $(RELEASE_FLAG)

docs-test:
ifneq ($(wildcard tools/site/tests),)
	$(SITE_ENV) $(PYTHON) -m unittest discover -s tools/site/tests
else
	@echo "docs-test: no tools/site/tests directory, nothing to run"
endif

# --strict: any warning of Zensical (broken link or anchor, ...) fails the build.
docs-build: docs-test
	$(PYTHON) tools/site/build.py --strict $(RELEASE_FLAG)
	$(PYTHON) tools/site/check_site.py $(SITE_DIR) $(CHECK_FLAGS) $(RELEASE_FLAG)

# One release at a time: the links of the release selector to the other
# releases do not work in this preview. For the whole portal: docs-preview.
docs-serve:
	$(PYTHON) tools/site/build.py --serve --dev-addr $(DEV_ADDR) $(RELEASE_FLAG)

docs-preview:
	$(PYTHON) tools/site/serve_site.py $(SITE_DIR) --addr $(DEV_ADDR)

# The downloaded Mermaid bundle is a dependency, not a build product: it stays.
docs-clean:
	rm -rf $(SITE_DIR) .cache .build .zensical.*.toml docs/*/assets/data/updates.json
	find tools -type d -name __pycache__ -prune -exec rm -rf {} +
