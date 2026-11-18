# Vendored Mermaid

The site serves the browser bundle of [Mermaid](https://github.com/mermaid-js/mermaid) **12.3.0** from this directory,
as `mermaid.min.js`. The file is the unmodified `package/dist/mermaid.min.js` of the npm package `mermaid@12.3.0`.
Licence: MIT, see `LICENSE` (copied from the same package).

`mermaid.min.js` is **not committed** (5.5 MB, git-ignored). `tools/site/fetch_vendor.py` downloads the pinned
tarball from the npm registry, verifies it and writes the file here. `tools/site/prebuild.py` runs that step before
every build, so `make docs-build` is enough; nothing is downloaded when the file is already in place.

| | |
|---|---|
| **Version** | 12.3.0 |
| **Tarball** | `https://registry.npmjs.org/mermaid/-/mermaid-12.3.0.tgz` |
| **Tarball integrity (npm registry, `dist.integrity`)** | `sha512-4113TdXeLAsMruJ79OpFL5O8+LTFXhQqZ260rF3tgUmiNAtRm4Uume04I+65PRN6yZ69J4f8rVYWW8zRk65UYw==` |
| **File in the tarball** | `package/dist/mermaid.min.js` |
| **SHA-256 of `mermaid.min.js`** | `336df803d87a38b70a01e736e666c8f7601d2ce42f5e47c8fafe5d721074b9a3` |
| **Size of `mermaid.min.js`** | 5 537 838 bytes |

The same values are constants of `tools/site/fetch_vendor.py`; a unit test compares the two.

```bash
python3 tools/site/fetch_vendor.py            # fetch when the file is missing or different
python3 tools/site/fetch_vendor.py --check    # verify the file in place, no network
python3 tools/site/fetch_vendor.py --tarball /path/to/mermaid-12.3.0.tgz   # without network access
```

## Why it is vendored

The portal makes no request to a third-party host. The theme bundle renders `mermaid` code blocks and, when
`window.mermaid` is not defined, downloads `https://unpkg.com/mermaid@12/dist/mermaid.min.js`. `overrides/main.html`
therefore loads this file, only on pages that contain a diagram, before the bundle looks for it. The build machine
needs `registry.npmjs.org` once; the reader's browser never leaves the site.

The theme asks for the Mermaid **12** release line: stay on 12.x unless the theme changes.

## How to update

1. Read the values of the new version from the registry:

   ```bash
   npm view mermaid@12 version dist.tarball dist.integrity
   ```

2. Put the version and the integrity value in `VERSION` and `TARBALL_INTEGRITY` of `tools/site/fetch_vendor.py`.
3. Run `python3 tools/site/fetch_vendor.py`. It stops on the SHA-256 of the extracted file and prints the value it
   found: after checking that the tarball integrity was accepted, put that value in `FILE_SHA256`, then run the
   script again.
4. Update the version, tarball URL, integrity, SHA-256 and size in the table above, and `LICENSE` if the package
   changed it.
5. Build the site and check a page of each diagram type used in `docs/` (flowchart, sequence diagram, Gantt chart,
   quadrant chart) in the light and the dark scheme.

This file is excluded from the site (`exclude_docs` in `zensical.toml`).
