# OzarLand · Kolla-Ansible Academy learning kit

**A shared land for better OpenStack operations.** This asset set supports a beginner-friendly learning portal for understanding what Kolla-Ansible changes in a running OpenStack cloud. Its tone is professional, warm and lightly playful: Lumo walks beside learners, explains what is known, and is honest about what still needs checking.

## Lumo character sheet

**The name.** "Lumo" comes from *lumen*, Latin for light: like the lantern Lumo carries, the Academy sheds light on
what Kolla-Ansible really does. The site says so on the portal welcome page and on the home page of each release.

Lumo is an original, gender-neutral cartographer-scholar and guide. The consistent design uses wavy brown hair, a parchment shirt, navy cape with one white cloud emblem, leather satchel with scrolls, small compass, practical boots and a brass lantern. Keep the same face, outfit, proportions and palette across every pose. The mood is patient, kind, calm and confident. Lumo is a companion for adult beginners: never a childlike mascot, a lecturer, or an alarmist.

Lumo is patient and encouraging, honest about uncertainty, and explicit when the source does not establish an answer. Explain one idea at a time. Invite a safe next step; do not imply that a potentially disruptive command is harmless.

### Short UI voice examples

- **Welcome:** “Hi, I’m Lumo. We’ll take this one step at a time.”
- **Explain:** “Let’s see what this command changes before you run it.”
- **Unknown:** “I can’t confirm that from this source alone. Let’s check the task and its defaults.”
- **Caution:** “Pause here: this step can affect a running service. Review the impact first.”
- **Checkpoint:** “You’ve got the main idea. Ready to try it in the lab?”

## Asset use

### Mascot poses

Use `mascot/welcome.png` in the first-run welcome, `pointing.png` beside short explanatory copy, `thinking.png` for open questions, `caution.png` beside carefully reviewed risk notes, `reading.png` on source-reading lessons, `celebrating.png` after small milestones, `lab.png` on hands-on practice pages, and `map.png` to introduce the journey. Use `avatar.png` as the 256 px portrait in compact author or guide callouts. The pose PNGs have transparent backgrounds and are sized for reusable UI placement; leave visible breathing room and do not crop the lantern, hands or feet.

### Journey scenes

`journey/journey-map.webp` is the complete, unlabeled five-stop overview. `stage-1.webp` through `stage-5.webp` are close-ups for the harbour welcome, library understanding, workshop practice, lighthouse risk judgement and observatory mastery. Put UI labels outside the artwork so the scenes remain language-independent.

### Badges

`badges/level-discover.svg`, `level-practise.svg` and `level-master.svg` identify learning levels in navigation or progress summaries. `stage-1.svg` through `stage-5.svg` are award seals for completing each journey stop. `journey-complete.svg` is the overall completion seal. These are flat scalable SVGs; preserve their clear space and do not add lettering inside them.

### Callout icons

Use `callouts/guide-tip.svg` for a guide note, `why-it-matters.svg` for operational context, `try-in-lab.svg` for a practice activity, `checkpoint.svg` for a pause and review, `careful.svg` for risk content, `remember.svg` for a durable takeaway, and `quiz.svg` for a knowledge check. Pair every icon with visible text; do not rely on color alone to convey meaning.

### Spot illustrations

Use `spots/empty-search.png` for an empty search result, `page-end.png` at the end of a lesson to point to the next path, and `well-done.png` after a learner completes a task. Keep these compact transparent scenes near the relevant message rather than using them as page backgrounds.

## Visual rules

Keep the established OzarLand palette: navy `#1F3A6B`, parchment `#F3E3C3`, parchment-soft `#FBF4E4`, wood `#C4904F`, wood-dark `#6B4220`, lantern `#F0B440`, sea `#1E9FB5`, terracotta `#B55A3A`, sky `#2F6FD0`, and green `#2C7A43`. The painted scenes use bright sky, turquoise water, white stone, terracotta roofs, navy cloud pennants, wood, brass lanterns and vines. Use illustrations as supporting guidance; place body text on tested solid surfaces and keep all in-image lettering out of the artwork.

Keep Lumo secondary to the lesson content. Choose the pose that matches the moment, not as decoration on every screen. Use a clear text alternative from `manifest.json`; decorative uses may use empty alt text in the product markup. Avoid redrawing, recoloring, distorting, or cropping Lumo in a way that removes the gesture or lantern. `previews/contact-sheet.png` is for review only and is not a page asset.

## File formats and dimensions

Mascot and spot scenes are transparent PNGs. The island map and stage scenes are WebP quality 82. Level shields are 64×64 SVGs, achievement seals are 96×96 SVGs, and callout symbols are 48×48 SVGs. `manifest.json` records dimensions, intended use and one factual English alt sentence for every delivered file. This package contains only assets with no text, letters or numbers inside the artwork; the filenames shown on the contact sheet are review labels outside the images.

## Where the kit is used in this repository

Site files: `overrides/assets/images/ozarland/` (mascot and spot scenes converted to WebP with transparency, 400 px and
600 px wide; journey scenes recompressed). The emblems of the stage seals are centred in their circle.

| Kit file | Site file | Used by |
|---|---|---|
| `mascot/welcome.png` | `lumo/welcome.webp` | home page of each release (`overrides/home.html`) |
| `mascot/pointing.png` | `lumo/pointing.webp` | welcome page of the portal (`overrides/landing.html`); quiz or challenge score with a wrong answer |
| `mascot/map.png` | `lumo/map.webp` | journey page (`overrides/journey.html`) |
| `spots/well-done.png` | `lumo/well-done.webp` | journey page, when every page is read |
| `mascot/caution.png` | `lumo/caution.webp` | pages of an operation rated Critical (`impact: [critical]`) |
| `mascot/celebrating.png` | `lumo/celebrating.webp` | end of a journey page, once it is marked as read; quiz or challenge passed |
| `mascot/reading.png` | `lumo/reading.webp` | glossary page; "To remember" cards |
| `mascot/lab.png` | `lumo/lab.webp` | journey page, "Practise safely"; "What would you do?" scenarios |
| `mascot/thinking.png` | `lumo/thinking.webp` | "Check yourself" quizzes, final challenges of the stages |
| `journey/journey-map.webp`, `stage-1.webp` … `stage-5.webp` | `journey/` | journey page |
| `badges/level-*.svg` | `badges/` | level chip of every page |
| `badges/stage-*.svg`, `journey-complete.svg` | `badges/` | seals of the journey page |
| `callouts/*.svg` | `callouts/` | callouts guide, why, lab, checkpoint, careful, remember, quiz, scenario |
| `spots/empty-search.png` | `lumo/empty-search.webp` | search without result: `learning.js` adds Lumo's help to the search dialog of the theme (template `#oz-empty-search` of `overrides/main.html`) |
| `spots/page-end.png` | `lumo/page-end.webp` | end of every journey page, next to "ready for the next step?" |

Not used: `mascot/avatar.png` (`lumo/avatar.webp`), which the `page-end` scene replaced at the end of the journey pages; it
stays available for a compact guide callout.
