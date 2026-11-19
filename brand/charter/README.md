# OzarLand Kolla-Ansible Academy — graphic charter

This charter gives the existing static Zensical / Material-like documentation a coherent journey through OzarLand. The layout stays close to the generated Markdown page structure. It uses theme custom properties and small template hooks; no JavaScript framework or page-layout rebuild is needed.

## Design principles

- **Guide the work.** The island metaphor gives each documentation area a familiar district. It never replaces the literal navigation label, page title, severity text or source evidence.
- **Keep technical reading calm.** Body copy, long tables and command lines sit on solid surfaces. Painted scenes appear in hero strips, margins, empty states and the footer only.
- **Make evidence visible.** `CODE` means the source directly proves the statement. `NOT AVAILABLE` means the source reviewed does not establish it. A tint never carries this distinction alone.
- **Walk with beginners.** Lumo is a patient guide, not an authority voice. State uncertainty plainly, explain why a step matters and give a safe next action.
- **Respect the existing site.** Keep the current header/sidebar/content structure, content width and Markdown semantics. Prefer CSS properties and small templates over custom page markup.

## Districts

Every district has a stable accent, a flat emblem, a single-colour navigation tab icon, a painted banner and a short motto. At narrow widths, retain the district title and icon and crop the banner around its focal point.

| Site section | District | Accent | Motto | Art and navigation assets |
|---|---|---|---|---|
| Home / Start | **Harbour** | `#1E9FB5` | Every safe journey starts here. | `districts/harbour-banner.webp` · `districts/harbour-emblem.svg` · `icons/tab-harbour.svg` |
| Learning journey | **Island Map** | `#2F6FD0` | One clear step at a time. | `districts/map-banner.webp` · `districts/map-emblem.svg` · `icons/tab-map.svg` |
| Concepts | **Library & Observatory** | `#1F3A6B` | See how the pieces connect. | `districts/library-banner.webp` · `districts/library-emblem.svg` · `icons/tab-library.svg` |
| Operations | **Workshop** | `#C4904F` | Know what your command changes. | `districts/workshop-banner.webp` · `districts/workshop-emblem.svg` · `icons/tab-workshop.svg` |
| Troubleshooting | **Bridge Watch** | `#2C7A43` | Inspect calmly. Find a way through. | `districts/bridge-banner.webp` · `districts/bridge-emblem.svg` · `icons/tab-bridge.svg` |
| Risk and impact | **Lighthouse** | `#B55A3A` | Pause and understand the impact. | `districts/lighthouse-banner.webp` · `districts/lighthouse-emblem.svg` · `icons/tab-lighthouse.svg` |
| Components | **Citadel** | `#1F3A6B` | Services stand on shared foundations. | `districts/citadel-banner.webp` · `districts/citadel-emblem.svg` · `icons/tab-citadel.svg` |
| Reference | **Archives** | `#6B4220` | Find the source behind the claim. | `districts/archives-banner.webp` · `districts/archives-emblem.svg` · `icons/tab-archives.svg` |

The accent is for emblems, active-tab indicators, small rules and decorative map marks. Do not set small text directly in an accent colour on parchment. Use the tokenized text colour and keep the district name visible beside the icon.

## Palette and theme use

| Brand colour | Hex | Use |
|---|---|---|
| Navy | `#1F3A6B` | Main brand, links, active path and light-mode primary actions. |
| Navy strong | `#152A50` | Headings, body text and the light-mode top bar. |
| Parchment | `#F3E3C3` | Warm inset surfaces, code text and low-emphasis panel fills. |
| Parchment soft | `#FBF4E4` | Light-mode page canvas and text plate over imagery. |
| Wood | `#C4904F` | Dividers, brass/wood details and progress accents. |
| Wood dark | `#6B4220` | Archive accent, visited links and evidence seal details. |
| Lantern | `#F0B440` | Focus halo, lantern glows and small progress details. |
| Sea | `#1E9FB5` | Harbour accent and decorative water details. |
| Terracotta | `#B55A3A` | Lighthouse accent and risk illustrations. |
| Sky | `#2F6FD0` | Map accent and information-state border. |
| Green | `#2C7A43` | Bridge accent and positive/tip-state border. |

The default scheme uses a solid parchment-soft canvas (`#FBF4E4`), white reading cards and navy text. Slate uses `#11151A` for the page canvas, `#1C2433` for cards and parchment text. Dark variants of district accents are brighter values in the token file so icons and active rules remain visible. The original brand palette remains available as `color.*` tokens in both modes.

Status panels use pale, distinct fills in light mode and deep, distinct fills in dark mode. Each includes a written label and an icon. `CODE` and `NOT AVAILABLE` also keep explicit text and border shape; colour is a secondary cue. `Caution` is reserved for irreversible, high-impact or production-sensitive actions.

## Typography

- **Body and interface:** `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`; 1rem / 1.65 line-height. This avoids a network font dependency and stays readable in dense documentation.
- **Headings only:** **Lora Bold**, a warm, sturdy display serif that echoes the charter’s book-and-archive motif without making technical passages ornate. The self-hosted WOFF2 and SIL Open Font License are in `fonts/`. It is local only; do not add a Google Fonts request. Fallback: Georgia, serif.
- **Code:** `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`; 0.875rem / 1.55. Keep command spelling and punctuation intact.

| Element | Size | Weight | Line-height |
|---|---:|---|---:|
| H1 | 2.5rem (mobile 1.875rem) | 700 | 1.18 |
| H2 | 1.875rem (mobile 1.5rem) | 700 | 1.25 |
| H3 | 1.375rem | 700 | 1.3 |
| H4 | 1.125rem | 700 | 1.35 |
| Body and list | 1rem | 400 | 1.65 |
| Small / caption | 0.8125rem | 400 or 600 | 1.45 |
| Table | 0.875rem (mobile 0.8125rem) | 400 | 1.5 |
| Code | 0.875rem | 400 or 600 | 1.55 |

H2 gets a 0.2rem wood-colour rule with a small district emblem before it; H3 is plain. Links are underlined in body text. Hover strengthens the underline, visited links use the wood-dark token in light mode and a brighter terracotta tint in slate, and keyboard focus has a double lantern treatment. Never rely on hue alone to indicate a link or state.

## Layout, spacing and shape

Use the `space.*` tokens: 0.25, 0.5, 0.75, 1, 1.5, 2, 3 and 4rem. Keep prose at 68–76 characters per line. Desktop content max-width is 76rem; the main reading column is 48–54rem with a 16–19rem sidebar. At 360–767px, collapse the sidebar into the theme’s navigation drawer, reduce outer gutters to 1rem and stack cards. The document must not scroll horizontally; only a wide table frame or code block may scroll inside its own labeled region.

| Element | Spec |
|---|---|
| Header | 4.875rem desktop; 4rem mobile. Solid navy-strong in light mode, deep blue-black in slate. Keep search, release selector and theme switch reachable. |
| Tabs | 2.75rem tall, 0.75rem horizontal padding; icon 1.25rem, text label always present. Current district gets a 0.2rem lantern rule and `aria-current`. |
| Sidebar | 0.875rem labels, 2.5rem minimum row height, 0.2rem leading current-page rule; collapse below 48rem. |
| Breadcrumb | 0.8125rem, 0.5rem gaps, 1.5rem after; current location is plain text. |
| Cards / callouts | 0.875rem radius; 1px border; 1rem–1.5rem padding. No ornamental card shadow in dense reading areas. |
| Hero / illustration | 1.25rem radius; 1.5rem inset title plate; crop to keep the scene focal point. A district index banner is 10–14rem tall; article pages use a 4–6rem compact strip. |
| Borders | 1px solid `color.border`; use a 2px status-colour rail for callouts. |
| Shadows | `shadow.card` only for floating cards; `shadow.popover` for definition popovers and search suggestions. Avoid repeated elevation. |
| Buttons | 2.75rem minimum height, 0.75rem radius, 1rem x 1.25rem padding. Primary is filled brand; secondary is a bordered surface; quiet is an underlined text action. Disabled buttons retain a readable label and no hover motion. |

## Global shell

- **Header and tabs:** Keep the brand cloud mark and portal name at the start of the header. Show five or fewer high-level tabs; district icons supplement literal labels. The selected state has both a gold rule and `aria-current`.
- **Sidebar and breadcrumbs:** Maintain nested heading order. Current page is bold and marked with a side rule; breadcrumbs show the route, not an icon-only sequence.
- **Search:** A labeled input with a visible focus ring. Suggestions are a raised card with title, section path and matching snippet. Empty results use `pages/empty-search.webp` beside a short recovery suggestion.
- **Release selector:** A 2.75rem control with the selected release written out. Keep stable menu width and announce the selected version in the control name.
- **Theme switch:** A labeled button with sun/moon icon and the next mode named for screen readers. Persist through the theme framework if already supported.
- **Footer:** Use `ui/footer-skyline.svg` as a low-contrast decorative silhouette above the existing links. It is `aria-hidden` and never a text backdrop.

## Page headers and images

District landing pages show an H1 followed by that district’s 10–14rem banner. Article pages use the compact 4–6rem crop. On any hero, title text sits in a solid parchment-soft plate; no paragraph or technical statement overlays painted detail. The transparent margin texture is only an optional body-edge or hero treatment and should stay nearly invisible. It must not appear underneath prose, tables or code.

| Asset | Intended use |
|---|---|
| `districts/*-banner.webp` | District landing strip, crop with a calm left third for the title plate. |
| `districts/*-emblem.svg` | District card, page header and small map stop; use at 2–3rem. |
| `icons/tab-*.svg` | Navigation tabs, 1–1.25rem; currentColor inherits accessible text colour. |
| `ui/divider-path.svg` | Decorative break between lessons; hide from assistive tech. |
| `ui/texture-parchment.webp` | Optional, very low-contrast texture on margins or hero only. |
| `ui/footer-skyline.svg` | Footer silhouette; currentColor at low opacity and aria-hidden. |
| `pages/404.webp` | Lost-page recovery scene, with Lumo and the return action outside the artwork. |
| `pages/empty-search.webp` | Empty search results; keep suggestions and query state as live HTML beside it. |
| `pages/coming-soon.webp` | Unavailable release page; explain the selected version in live text. |

## Reading and source components

- **Paragraphs and lists:** 1rem body, 1.65 leading, 0.75rem paragraph gap. Ordered lists use `ui/step-stone-1.svg` … `9.svg` as decorative markers; CSS inserts the list number as real text. Keep the semantic ordered list and native number available.
- **Tables:** 0.875rem text, 1px borders, sticky header with `surface-muted`, alternating rows at low contrast. On narrow screens, wrap the table in a labeled `overflow-x:auto` region and preserve the first column if the theme supports it. Do not shrink columns until headers become unreadable.
- **Code:** Inline code uses a parchment inset with a fine border. Blocks use the deep chalkboard/brass-plate surface from the tokens; use 0.875rem monospace, 1.55 leading and a visible copy button. Only the code region may scroll horizontally. Command lines show the exact command plus an optional prompt marker in a separate visual column.
- **Keyboard keys:** `<kbd>` uses a small raised surface, 1px border and 0.2rem radius; do not substitute a key symbol for the written key name.
- **Footnotes:** 0.8125rem with a divider and a visible return link; keep reference numbers in the text.
- **Path divider:** `ui/divider-path.svg` signals a lesson boundary, not a semantic heading.
- **Mermaid:** Use white/parchment nodes in light mode and raised slate nodes in dark mode. Links use navy/sky with 2px line weight and arrowheads; labels use the text token. Keep node text literal and ensure node and connector contrast, with a text explanation if diagram reading is essential.
- **Figures:** Image alt text states the visible subject, not what the image means. Captions are 0.8125rem, placed on a solid surface.

## Callouts and admonitions

Every callout has an icon, a written heading and body text; the border/fill is only an extra cue. Use 2px left rail, 0.75rem radius, 1rem padding. Standard note, tip, important, warning and caution use their corresponding status tokens. The learning callouts reuse the matching existing line icons in `callouts/` and use the same state palette: guide tip (lantern), why it matters (compass), try in lab (flask/cloud), checkpoint (flag), careful (lighthouse beam), remember (scroll) and quiz (book/question cloud). Lumo appears only inside the Guide callout and speech bubbles. Keep callouts short and do not place one inside another.

## Chips, evidence and impact

Chips are 1.5rem high, pill radius, 0.5rem horizontal padding, 0.75rem text; wrap naturally. Keep the literal labels `read-only`, `writes-config`, `pulls-images`, `restarts-on-drift`, `recreates-containers`, `critical`, `maintenance-window` and `recovery`. Always render severity as Low, Medium, High or Critical in addition to its colour. `CODE` and `NOT AVAILABLE` are uppercase text labels with distinct icon/outline treatments. The latter means “not established by the reviewed source”, never “does not happen”.

## Learning UI

- **Journey bar:** “Stage 2 of 5 · page 3 of 4” stays plain text beside the progress bar. The bar is 0.625rem high and has a visible label for assistive tech.
- **Mark as read:** use a native checkbox with its full text label and 1.25rem hit target.
- **Previous / next:** secondary and primary buttons, full width on narrow screens, labels name the destination or lesson.
- **Stage seals:** `seal-locked.svg` is muted and locked; `seal-progress.svg` has an open progress ring. Completed seals use the district emblem and check mark, not a colour-only state. Keep stage names in HTML beside each seal.
- **Quiz:** Put the question in a card, choices in full-width selectable rows, and a text explanation after an answer. Correct and incorrect states have icon + label. Keep a gentle reveal, never a shake or red-only feedback.
- **Definitions:** On hover or keyboard focus, show a raised popover with the term and concise definition. It must also be available on touch and must not be hover-only.
- **Lumo bubbles:** Neutral uses parchment; caution uses the warning surface; celebration uses the tip surface. Keep the speech text live HTML and the character image decorative.

## Special pages

- **Release home:** Start at the Harbour, say which release is selected, show the primary “Begin the journey” action and the five learning stages below.
- **Portal welcome:** Explain what source code learners will inspect, how to use the stage path and how to find the upstream release. Use the Harbour banner and a Guide callout.
- **Journey:** Use the island map, then five separately titled stage cards. On mobile, stack the stages and keep the progress label visible.
- **404:** Say the page could not be found, show Lumo in the scene and provide a clear return-to-Harbour action. Do not blame the reader.
- **Coming soon:** State the release or section that is unavailable, offer another supported release and keep Lumo encouraging.
- **Empty search:** Repeat the query in live text, state that there are no matches and offer spelling, section and clear-search actions.

## CSS-only motion

Seal completion uses a restrained 420ms scale-and-settle stamp, with no rotation beyond 4 degrees. Focused lantern controls get a 220ms soft glow that stops on blur. Quiz answer explanation uses a 220ms opacity/height reveal, not a page-turn that moves nearby content. Every motion has a `prefers-reduced-motion: reduce` override that removes animation and transition while preserving the final state.

## Accessibility contrast table

Ratios below are computed from the exact sRGB token pairs with the WCAG relative-luminance formula. Body and other text pairs target at least 4.5:1. The focus pair is a non-text UI indicator and targets 3:1. The default focus ring is double-layered: the navy outer line is the high-contrast indicator; the lantern-gold inner halo is decorative. Slate uses lantern gold as the indicator. No failing pair is used for text or state.

| Scheme | Foreground role | Foreground | Background | Ratio | Result |
|---|---|---|---|---:|---|
| default | Body / headings | `#152A50` | `#FBF4E4` | 12.96:1 | PASS |
| default | Secondary text | `#1F3A6B` | `#FFFFFF` | 11.20:1 | PASS |
| default | Muted text | `#4E5A6D` | `#FFFFFF` | 6.98:1 | PASS |
| default | Link | `#1F3A6B` | `#FBF4E4` | 10.22:1 | PASS |
| default | Visited link | `#6B4220` | `#FBF4E4` | 7.90:1 | PASS |
| default | Header text | `#FBF4E4` | `#152A50` | 12.96:1 | PASS |
| default | Primary button | `#FBF4E4` | `#1F3A6B` | 10.22:1 | PASS |
| default | Secondary button | `#152A50` | `#F3E3C3` | 11.22:1 | PASS |
| default | Disabled control label | `#566170` | `#E8DFCF` | 4.76:1 | PASS |
| default | Inline/code block text | `#F3E3C3` | `#152A50` | 11.22:1 | PASS |
| default | Info callout | `#152A50` | `#E2EFFB` | 12.15:1 | PASS |
| default | Tip callout | `#152A50` | `#E4F1E5` | 12.18:1 | PASS |
| default | Important callout | `#152A50` | `#FFF0C6` | 12.53:1 | PASS |
| default | Warning callout | `#152A50` | `#F9E9DA` | 11.97:1 | PASS |
| default | Caution callout | `#152A50` | `#F4E1DB` | 11.25:1 | PASS |
| default | Evidence CODE | `#FFFFFF` | `#1F3A6B` | 11.20:1 | PASS |
| default | Evidence NOT AVAILABLE | `#FFFFFF` | `#6B4220` | 8.66:1 | PASS |
| default | Impact chips | `#152A50` | `#E2EFFB` | 12.15:1 | PASS |
| default | Impact chips | `#152A50` | `#E4F1E5` | 12.18:1 | PASS |
| default | Impact chips | `#152A50` | `#FFF0C6` | 12.53:1 | PASS |
| default | Impact chips | `#152A50` | `#F9E9DA` | 11.97:1 | PASS |
| default | Impact chips | `#152A50` | `#F4E1DB` | 11.25:1 | PASS |
| default | Severity chips | `#152A50` | `#E4F1E5` | 12.18:1 | PASS |
| default | Severity chips | `#152A50` | `#FFF0C6` | 12.53:1 | PASS |
| default | Severity chips | `#152A50` | `#F9E9DA` | 11.97:1 | PASS |
| default | Severity chips | `#152A50` | `#F4E1DB` | 11.25:1 | PASS |
| slate | Body / headings | `#F3E3C3` | `#11151A` | 14.47:1 | PASS |
| slate | Secondary text | `#D6DFED` | `#1C2433` | 11.59:1 | PASS |
| slate | Muted text | `#B2BDCA` | `#1C2433` | 8.17:1 | PASS |
| slate | Link | `#A9C7F2` | `#11151A` | 10.59:1 | PASS |
| slate | Visited link | `#F2A28B` | `#11151A` | 9.00:1 | PASS |
| slate | Header text | `#FBF4E4` | `#152038` | 14.79:1 | PASS |
| slate | Primary button | `#11151A` | `#8FB0E6` | 8.31:1 | PASS |
| slate | Secondary button | `#F3E3C3` | `#253249` | 10.17:1 | PASS |
| slate | Disabled control label | `#B2BDCA` | `#283140` | 6.88:1 | PASS |
| slate | Inline/code block text | `#F3E3C3` | `#152038` | 12.80:1 | PASS |
| slate | Info callout | `#F3E3C3` | `#1D3147` | 10.48:1 | PASS |
| slate | Tip callout | `#F3E3C3` | `#21382E` | 9.93:1 | PASS |
| slate | Important callout | `#F3E3C3` | `#3A301B` | 10.25:1 | PASS |
| slate | Warning callout | `#F3E3C3` | `#3B2B22` | 10.67:1 | PASS |
| slate | Caution callout | `#F3E3C3` | `#3B2525` | 11.23:1 | PASS |
| slate | Evidence CODE | `#11151A` | `#8FB0E6` | 8.31:1 | PASS |
| slate | Evidence NOT AVAILABLE | `#11151A` | `#D9A865` | 8.50:1 | PASS |
| slate | Impact chips | `#F3E3C3` | `#1D3147` | 10.48:1 | PASS |
| slate | Impact chips | `#F3E3C3` | `#21382E` | 9.93:1 | PASS |
| slate | Impact chips | `#F3E3C3` | `#3A301B` | 10.25:1 | PASS |
| slate | Impact chips | `#F3E3C3` | `#3B2B22` | 10.67:1 | PASS |
| slate | Impact chips | `#F3E3C3` | `#3B2525` | 11.23:1 | PASS |
| slate | Severity chips | `#F3E3C3` | `#21382E` | 9.93:1 | PASS |
| slate | Severity chips | `#F3E3C3` | `#3A301B` | 10.25:1 | PASS |
| slate | Severity chips | `#F3E3C3` | `#3B2B22` | 10.67:1 | PASS |
| slate | Severity chips | `#F3E3C3` | `#3B2525` | 11.23:1 | PASS |

Focus indicator check: default navy outer ring on canvas is **12.96:1**; slate lantern ring on canvas is **9.87:1**. Decorative accent fills are not used as text backgrounds. A raw brand accent on parchment may fail for small text; keep text on the documented surface tokens instead. Contrast table failures: **0**.

Brand accent check against the light canvas (forbidden as body text when marked fail):

| Brand accent used as foreground | Foreground | Background | Ratio | Use |
|---|---|---|---:|---|
| navy | `#1F3A6B` | `#FBF4E4` | 10.22:1 | PASS |
| navy-strong | `#152A50` | `#FBF4E4` | 12.96:1 | PASS |
| wood | `#C4904F` | `#FBF4E4` | 2.57:1 | FAIL — decorative only |
| wood-dark | `#6B4220` | `#FBF4E4` | 7.90:1 | PASS |
| lantern | `#F0B440` | `#FBF4E4` | 1.69:1 | FAIL — decorative only |
| sea | `#1E9FB5` | `#FBF4E4` | 2.87:1 | FAIL — decorative only |
| terracotta | `#B55A3A` | `#FBF4E4` | 4.27:1 | FAIL — decorative only |
| sky | `#2F6FD0` | `#FBF4E4` | 4.45:1 | FAIL — decorative only |
| green | `#2C7A43` | `#FBF4E4` | 4.82:1 | PASS |

The five failing accent/canvas pairs above are explicitly decorative and are not used for small text. Wood, lantern and sea also fall below 3:1 for non-text indicators on the canvas. For captions and labels, use the semantic text tokens from the contrast table. The implemented text pairs still have **0 failures**.

## Do / don’t

| Do | Don’t |
|---|---|
| Keep body copy, tables and code on calm solid surfaces. | Put a painted scene, texture or gradient behind long technical text. |
| Name the visible cloud effect and point to the source task. | Let an island metaphor imply what a command does. |
| Pair colour with words, icons, borders or shape. | Use colour alone for risk, severity, evidence or progress. |
| Keep Lumo warm, brief and honest about unknowns. | Make Lumo perform uncertainty as a joke or promise safety without evidence. |
| Crop banners with clear space for a solid title plate. | Place small labels directly over busy painted detail. |
| Preserve semantic headings, table headers, labels and focus states. | Replace site navigation or keyboard behavior with custom visual-only controls. |

## Mockups and package map

`mockups/` contains light and dark examples for home, journey, a dense operation lesson and the 404 page at 1440px and 390px. The screenshots intentionally include normal HTML-style interface words, table values and code as a design preview. Standalone painted scenes and decorative illustrations contain no text, letters or numbers. The scene banner artwork is kept separate from live page headings, alerts, labels and controls.

`tokens/charter.css` contains only the light and slate selectors plus `--oz-*` custom property declarations. `tokens/charter.json` has the same scheme and token keys/values. Add these properties to the existing theme layer; do not use them to override the content structure.

### Font license

Lora is distributed under the SIL Open Font License 1.1. The full license is bundled at `fonts/OFL.txt`, next to the self-hosted WOFF2. The font is optional; if removed, headings fall back to Georgia. Upstream license source: https://github.com/google/fonts/blob/main/ofl/lora/OFL.txt.

## Where the charter is applied in this repository

Site files: `overrides/assets/images/ozarland/districts/` (banners resized to 1400×350 WebP, emblems, tab icons),
`ui/` (path divider, footer skyline, locked seal, path stone), `pages/` (404, coming soon, empty search, 1200×600),
`overrides/assets/fonts/` (Lora Bold and its licence). The styles are section 18 of
`overrides/assets/stylesheets/portal.css`; the palette of the charter replaces the former grey one in both schemes.

| Charter element | Where |
|---|---|
| District of a page | `oz_districts` in `overrides/main.html` (URL prefix → district) |
| Banner | index page of each section (whole banner); other pages of the section (thin strip) |
| Emblem | before each H2 of the content; the accent marks the current page in the sidebar |
| Tab icons | navigation tabs, in the order of the nav of a release |
| Header | navy in both schemes, parchment text |
| Lora Bold | H1, H2, H3, site title (self-hosted, `fonts/OFL.txt`) |
| Path stones | numbered lists at the top level of the content |
| Path divider | horizontal rules |
| Footer skyline | above the navy footer |
| Seals | journey page: locked (not started), the stage's seal dimmed (in progress), stamped (done) |
| `pages/404.webp`, `pages/coming-soon.webp` | not-found page, planned release pages |

Not applied: the dark "chalkboard" code blocks (the syntax colours of the theme are made for light code blocks),
`seal-progress.svg` (its check mark reads as "done"), `step-stone-2…9.svg` (identical to 1: the number is CSS text),
the parchment texture, `pages/empty-search.webp` (the search dialog of the theme has no hook for it).
