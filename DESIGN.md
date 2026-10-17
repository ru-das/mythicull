---
# NOTE (2026-10-17): superseded by the U2 "East of the Sun" restyle. This file still describes the Yellow Box look; `web/styles.css` tokens and docs/PROGRESS.md (UI restyle U2) are current until this is regenerated.
name: MythiCull
description: Film-stock packaging for a local culling desk. Yellow bar, red rule, black edge-print captions around neutral photos.
colors:
  film-yellow: "#ffb300"
  stop-red: "#d7261e"
  keep-green: "#35b36b"
  on-yellow: "#111111"
  edge-orange: "#ff7a1a"
  dark-bg: "#121212"
  dark-rail: "#0b0b0b"
  dark-panel: "#1b1b1b"
  dark-line: "#2e2e2e"
  dark-ink: "#f4f1e8"
  dark-muted: "#a39e92"
  dark-surround: "#262626"
  dark-tile: "#303030"
  dark-err: "#ff7468"
  light-bg: "#efece3"
  light-rail: "#fbf9f3"
  light-panel: "#ffffff"
  light-line: "#d6d1c3"
  light-ink: "#1a1814"
  light-muted: "#5d584d"
  light-edge-text: "#a84300"
  light-link: "#7a4f00"
  light-surround: "#d2d2d2"
  light-tile: "#bfbfbf"
  light-err: "#b3170f"
typography:
  display:
    fontFamily: "Archivo Black, Arial Black, sans-serif"
    fontSize: "clamp(26px, 2.6vw, 34px)"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  brand:
    fontFamily: "Archivo Black, Arial Black, sans-serif"
    fontSize: "26px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
  roll-name:
    fontFamily: "Archivo Black, Arial Black, sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 1.1
  title:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.15
  body:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.4
  label:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.03em"
  data:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tabular-nums"
rounded:
  xs: "2px"
  sm: "3px"
  md: "4px"
  pill: "12px"
  round: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  xl: "24px"
  xxl: "48px"
components:
  topbar:
    backgroundColor: "{colors.film-yellow}"
    textColor: "{colors.on-yellow}"
    height: "64px"
    padding: "8px 24px"
  button-primary:
    backgroundColor: "{colors.film-yellow}"
    textColor: "{colors.on-yellow}"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.stop-red}"
    textColor: "#ffffff"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "40px"
  button-outline-hover:
    backgroundColor: "{colors.dark-ink}"
    textColor: "{colors.dark-bg}"
  input:
    backgroundColor: "{colors.dark-rail}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "42px"
  segmented-on:
    backgroundColor: "{colors.film-yellow}"
    textColor: "{colors.on-yellow}"
    rounded: "{rounded.xs}"
    height: "34px"
  sidebar:
    backgroundColor: "{colors.dark-rail}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.md}"
    padding: "16px 14px"
    width: "300px"
  chapter-no-active:
    backgroundColor: "{colors.film-yellow}"
    textColor: "{colors.on-yellow}"
    rounded: "{rounded.xs}"
    typography: "{typography.data}"
  photo-grid:
    backgroundColor: "{colors.dark-surround}"
    rounded: "{rounded.md}"
    padding: "12px"
  edge-caption:
    backgroundColor: "{colors.dark-rail}"
    textColor: "{colors.edge-orange}"
    typography: "{typography.data}"
    padding: "6px 8px"
  group-count:
    backgroundColor: "{colors.film-yellow}"
    textColor: "{colors.on-yellow}"
    rounded: "{rounded.pill}"
    height: "24px"
  group-badge:
    backgroundColor: "{colors.stop-red}"
    textColor: "#ffffff"
    rounded: "{rounded.round}"
    size: "20px"
  toast:
    backgroundColor: "#111111"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
---

# Design System: MythiCull

## Overview

**Creative North Star: "The Film Roll"**

Every shoot is a roll of film. The chrome is film-box packaging: a yellow top bar over a red rule, black edge-print strips under each frame, and orange mono frame numbers. The photos sit on a neutral grey surround that no theme color touches. The interface frames the pictures and then gets out of the way, so a keyboard-driven evening cull stays calm.

The world is dark by default (near-black ground, off-white ink) with a light theme (cream ground, same yellow bar, same grey photo surround). Density is working-tool dense: a 300px chapter sidebar, a 190px-minimum thumbnail grid, 13-14px counters. Three typefaces split the jobs: Archivo Black for names, Barlow Semi Condensed for controls and prose, Martian Mono for anything that reads like edge print or data.

The build departs from the original contract in these ways, and the build wins. Keep is green, not off-white (it matches the XMP Green label). The chapter rail is a bordered sidebar card, not a flush full-height black column. Counters sit in the action strip under the bar, not in the bar. Frame captions read `<n>A` with a constant `A` suffix; it is edge-print decoration and carries no chapter meaning (chapter rolls are numbered `01A`, `02A` in the sidebar, and `ALL` for the unfiltered view).

**Key Characteristics:**
- Yellow bar (64px) with a 6px red bottom rule is the only full-bleed color; it stays yellow in both themes.
- Photos on a neutral grey surround (#262626 dark, #d2d2d2 light); no hue near a photo.
- Frame captions are black strips with orange Martian Mono: a notch marker, `<n>A`, filename, keep/reject mark, stars.
- Custom controls everywhere; no browser-native widgets. All are keyboard-operable with real roles.
- Motion is springy (one `cubic-bezier(.16, 1, .3, 1)` curve) and fully neutralised by `prefers-reduced-motion`.

## Colors

Film-box primaries (yellow, red, black) plus a signal green, over two neutral themes selected by `data-theme` on the root element (persisted in `localStorage` as `mythicull-theme`).

### Primary
- **Film Yellow** (`film-yellow`): top bar, primary buttons, selected segment, active chapter number, slider fill/thumb ring, progress fill, stars, pick outline, group-count pill, focus border on fields, text selection. Dark text on it is always `on-yellow`.
- **Stop Red** (`stop-red`): 6px rule under the bar, group badge, primary-button hover, search focus ring, error toast border. Rejected cells use a slightly brighter `#e5392f` ring and `#ff5a4d` mark (see drift note).

### Secondary
- **Keep Green** (`keep-green`): keep state only: cell ring, mark, and lightbox chip. Matches the XMP Green label. Never decorative.

### Tertiary
- **Edge Orange** (`edge-orange`): frame numbers, the notch marker, lightbox index, always on black strips. In the light theme, orange text on cream uses `light-edge-text` instead (roll numbers, stepper values, active chapter count).

### Neutral
- **Dark:** ground `dark-bg`, rail/field `dark-rail`, cards `dark-panel`, hairlines `dark-line`, ink `dark-ink` (warm off-white), secondary text `dark-muted`, photo surround `dark-surround`, empty tile `dark-tile`, error text `dark-err`. Selection ring is the ink color.
- **Light:** ground `light-bg`, sidebar `light-rail`, cards/fields `light-panel`, hairlines `light-line`, ink `light-ink`, secondary text `light-muted`, links `light-link`, photo surround `light-surround`, tile `light-tile`, error `light-err`. Selection ring and focus ring are near-black (#111 / ink).

### Named Rules
**The Neutral Surround Rule.** Nothing but neutral grey touches a photo's edge. Status rings (green, red) hug the cell; the grid background never takes theme color.
**The Keep Is Green Rule.** Green means keep. Yellow means pick, star, group, or active. Red means reject or group badge. Off-white ring means selection. Do not reuse these across roles.
**The Bar Stays Yellow Rule.** The top bar is `film-yellow` with `on-yellow` ink and a red rule in both themes; focus rings inside it are #111.

## Typography

**Display Font:** Archivo Black (with Arial Black, sans-serif), vendored, weight 400
**Body Font:** Barlow Semi Condensed (with Arial Narrow, sans-serif), vendored, weights 500/600/700
**Label/Mono Font:** Martian Mono (with ui-monospace), vendored, weights 400/600

**Character:** Poster-weight names over a condensed workhorse UI face, with a wide mono for edge-print numerics. All fonts are served from `/fonts/` as woff2 with `font-display: swap`; no runtime network.

### Hierarchy
- **Display** (400, clamp(26px, 2.6vw, 34px), 1.05, -0.01em): page `h2`, balanced wrap.
- **Brand** (400, 26px, 1, -0.02em): wordmark in the bar, preceded by a black film-notch triangle.
- **Roll name** (400, 22px, 1.1): project names in the project list.
- **Title** (700, 17px, 1.15): `h3`, chapter titles.
- **Body** (500, 16px, 1.4): default UI text.
- **Label** (600, 14px, +0.03em): field labels, segmented buttons, switches.
- **Data** (Martian Mono 400/600, 11-13px, tabular-nums): frame numbers `14A`, chapter numbers, counters, roll numbers, folder paths, stepper values, lightbox caption. Counts of 20px in the project list.

### Named Rules
**The Three Voices Rule.** Display face for names only, condensed sans for everything operable, mono for anything numeric or edge-printed. Do not set paragraphs in Archivo Black or numbers in Barlow.
**The Tabular Rule.** Numbers that change (counters, frame numbers) use mono with tabular figures so digits do not shift.

## Layout

Fixed, sticky bar (64px minimum, wraps on narrow widths) over a `main` with 28px/24px padding and a 1900px content cap. The home view is a two-column grid (300-380px new-project card beside the roll list, 48px gap). The review workspace is a 300px sidebar plus fluid grid (20px gap), with a workbar above: Index photos action and progress, counters, search message, export panel toggle. The thumbnail grid is `repeat(auto-fill, minmax(190px, 1fr))` with 10px gaps and 12px inner padding; cells are 3:2 frames.

Spacing is an informal 4/8/12/16/18/24/48px rhythm, not tokenised in CSS. Both the new-project card and the sidebar are sticky below the bar.

Responsive: at 900px and below, columns collapse to one, the bar becomes static, the bar slot (search, filters) wraps to a full-width row, the sidebar hides behind a "Chapters and settings" toggle, and the grid minimum drops to 140px. At 600px and below, edge captions wrap, the mark moves right, and the filename drops to its own line.

## Elevation & Depth

Mostly flat: layers are told apart by tonal steps (ground, panel, rail) and 1px hairlines. Shadows appear only on state: the selected cell lifts 2px with a dark drop shadow, and toasts carry one ambient shadow. Focus is a ring, not a shadow.

### Shadow Vocabulary
- **Selection** (`box-shadow: 0 0 0 3px var(--sel), 0 6px 18px rgba(0,0,0,.5)`): selected cell. When also keep or reject, the status ring is inner and the selection ring outer (3px + 6px).
- **Toast** (`box-shadow: 0 10px 28px var(--shadow)`): transient notices.
- **Field focus** (`0 0 0 3px` yellow at 35%): inputs. Search in the bar uses `0 0 0 3px #111, 0 0 0 5px var(--red)`.

### Named Rules
**The Flat-Until-Chosen Rule.** Surfaces are flat at rest; lift is reserved for the selected frame and transient toasts.

## Shapes

Small, square-ish corners like card stock: 2px (indicator, frame cells), 3px (buttons, fields, segmented control, theme button), 4px (cards, sidebar, grid, toast). Pills (12px) are for the group-count; circles for the group badge, slider thumb and switch knob. Film-notch triangles (clip-path) mark the brand and each frame caption. Outlines are 2px for buttons, 1px hairlines for fields and cards.

## Components

All controls are authored, not native; each keeps real button/input semantics plus ARIA.

### Buttons
- **Shape:** 3px radius, 40px min height, 2px border, Barlow 700 15px.
- **Primary:** yellow fill, #111 text; hover turns red with white text.
- **Outline (default):** transparent with ink border; hover inverts to ink fill and ground text. Active presses down 1px and scales .98. Disabled is 45% opacity.
- **Text:** underlined link color, 600 weight; hover goes to ink.
- **Icon buttons:** theme toggle (40px black square, yellow icon), lightbox close (40px), stepper +/-, search clear. Icons are authored inline SVG, 2.2 stroke, never glyphs.

### Inputs / Fields
- **Style:** 42px min height, 1px hairline border, 3px radius, field-colored fill, 14px muted label above.
- **Focus:** border goes yellow with a 35% yellow halo. Bar search is a black rectangle with yellow icon and cream text; it gains a black+red double ring on focus.
- **Error:** `role="alert"` message in error color; the form shakes (translateX, 350ms) on invalid submit.

### Segmented control
`role="radiogroup"` of `role="radio"` buttons on a black track (3px padding); a sliding yellow indicator (`transform` and `width` transition, 350ms) follows the checked button. In-bar it is black; out of the bar it takes field fill and a hairline.

### Switch
`role="switch"` with `aria-checked`. 38x22 track, 14px knob that slides 16px and turns yellow when on. In workbar/panels the track is field-colored with a muted border that turns yellow when on.

### Stepper
Bordered group: minus button, centered orange-mono numeric input (64px), plus button; button hover fills yellow.

### Slider
`role="slider"`, focusable, with `aria-valuenow/min/max/text`; 4px track, yellow fill, ink thumb with 3px yellow ring that scales 1.18 on hover/drag. Pointer capture for dragging. Ends are labelled in 13px muted text (Sharp / Vibe).

### Panel (disclosure)
`aria-expanded` head button (outline style, chevron rotates 180deg) over a body that animates `grid-template-rows` 0fr to 1fr in 400ms; closed content is `visibility: hidden`. Body is a panel-colored card with 18px padding.

### Progress bar
`role="progressbar"`, 8px track, yellow fill with a 450ms width transition; while running, fill gets a looping horizontal sheen gradient.

### Chapter rail (sidebar)
Bordered card (rail fill, 4px radius) holding settings (gap stepper, vibe field, pick-weight slider, camera clocks when 2+ cameras) and the chapter list. Each row: mono number chip (`01A`, or `ALL`), 17px title, mono count. Inactive rows are muted; the active row sits on the panel color with a yellow number chip and edge-colored count. Active row also shows meta (photo and kept counts, "Use suggested name", "rename"). Inline rename swaps in a field in the row; blank resets.

### Photo cell and edge caption
A cell is a 3:2 frame on the tile color, with a black caption strip beneath: notch triangle, `<n>A` (mono 600), filename (ellipsized, warm grey), keep/reject mark, stars. Keep is a 3px green ring; reject is a 3px red ring with the image at 38% opacity; group pick is a 2px yellow outline offset 2px; selection per Elevation. Overlaid on the frame: red circular `!` badge (no EXIF time) at top left, yellow mono count pill (group size) at bottom right. Hover scales the image 1.03.

### Counters
Mono 13px muted line in the workbar: all / kept / rejected / unreviewed, with ink-colored values. Changed digits flip in (per-digit `flip` animation staggered 45ms by position). Container has an aria-label with the full sentence.

### Toast
Black card, hairline border, bottom-right stack in a polite `role="status"` region; errors use `role="alert"`, a dark red fill and red border. Enters from below, exits sliding right.

### Lightbox
`role="dialog" aria-modal="true"`: near-black 96% scrim, image contained in the viewport (scales from .96 on open, soft swap on navigation), black caption bar with orange index, mono filename, capture time, optional "file time, not EXIF" warning in yellow, Keep/Reject chip, key hint, and a 40px close button. Fades with visibility toggling.

### Navigation
Brand link on the left of the bar; the bar slot holds search, segmented filter, Best/All, and theme toggle (pushed right, sun/moon icon spins in). Project list rows are links with orange mono roll number, display-face name, mono folder, right-aligned count; hover tints the row and nudges its padding-left from 12px to 20px.

### Motion inventory
Shared curve `cubic-bezier(.16, 1, .3, 1)`. Keyframes: `view-in` (view enters, 500ms, 14px rise), `row-in` (project rows, staggered 50ms), `cell-in` (first 40 cells, staggered 22ms), `flip` (counter digits, 550ms), `stamp` (keep/reject mark, 500ms scale from 2.6 with -14deg), `pop` (star change), `sheen` (running progress), `toast-in`/`toast-out`, `shake` (invalid form), `spin-in` (theme icon), `lb-swap` (lightbox image change). Theme change fades background, color and border for 350ms via a temporary `theming` class. Transitions elsewhere are 150-500ms.
**Reduced motion:** under `prefers-reduced-motion: reduce` every animation and transition collapses to .001ms with zero delay (a global rule), so state still changes but nothing moves. Timers in JS (toast dismissal, class removal) are unaffected.

## Do's and Don'ts

### Do:
- **Do** keep the bar yellow with a 6px red rule and `on-yellow` ink in both themes.
- **Do** put every frame number and counter in Martian Mono with tabular figures; frame captions read `<n>A`.
- **Do** keep photo surround neutral grey in both themes.
- **Do** show keep as green, reject as red, selection as an off-white (dark) or near-black (light) ring.
- **Do** build new controls as authored elements with real roles, `aria-*` state, and a visible `:focus-visible` ring (2px, offset 2px).
- **Do** use authored inline SVG icons in the existing stroke style.
- **Do** route new animation through the shared easing and let the global reduced-motion rule neutralise it.

### Don't:
- **Don't** use browser-native selects, checkboxes, range inputs or dialogs.
- **Don't** tint the grid, thumbnails or lightbox image area with theme color.
- **Don't** treat the `A` in `14A` as meaningful data; it is edge-print decoration.
- **Don't** use yellow for keep or green for pick; roles are fixed.
- **Don't** set body copy in Archivo Black or use text glyphs as icons.

## Not canonized

Defects the build carries, not rules for new surfaces: reject red is hardcoded in three slightly different values (#d7261e bar/badge token, #e5392f ring/chip, #ff5a4d mark) instead of one token; several edge-strip colors (#0b0b0b, #ff7a1a, #8c7a68) and toast/bar blacks (#111) are hardcoded rather than tokenised; the light-theme sidebar is lighter than the page, which inverts the dark theme's darker-rail relation.
