# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Solo wedding and event photographers culling a shoot of roughly 1,000 to 3,000 frames at a desk, often in the evening, mostly by keyboard. Confirmed in the redesign request: long sessions, dark by default, light available.

## Product Purpose
MythiCull is a local-first culling app. It imports a shoot, indexes it with the open-weight EmbeddingGemma 2 model, groups photos into time-based story chapters and near-duplicate bursts, supports plain-English search, and exports picks as XMP sidecars or copied files. Success is a finished cull with every decision saved, without photos leaving the machine.

## Positioning
Runs fully offline after a one-time model download; culling is organised by story chapters and burst groups, not a flat grid.

## Operating Context
Photo folders are read-only. Browsing and rating work before indexing finishes and without the model. Decisions (keep, reject, stars) and renamed chapter titles are never overwritten by re-runs.

## Capabilities and Constraints
- Flow (unchanged by the redesign): project list and create-and-import, import progress, review workspace (chapter sidebar, top bar with search, Suggested/Every photo, filter, counters, grid, large preview), index job with cancel, XMP and copy export with summaries.
- Sidebar settings: chapter gap minutes, optional “What to look for” description and suggested photo priority, per-camera clock offsets (only with 2+ camera models), suggested chapter names.
- Keyboard: arrows, Enter/Space, Esc, P, X, U, 0-5, `/`, Ctrl/Cmd+Z, auto-advance.
- Stack: plain HTML, CSS, vanilla ES modules, no Node, no build step. No runtime network calls, so fonts must be served from the repo.
- Terminology: chapter, similar photos, suggested photo, keep, reject, analyze, description.

## Brand Commitments
Name: MythiCull. Mythic register (confirmed 2026-10-17): the interface draws on fairy tales (East of the Sun; no constellations, only simple icons and logos, per the user on 2026-10-17). Feature labels stay plain and humane (clear verbs and nouns); mythic voice appears only in secondary text: empty states, page headings such as the project list, toasts, and loading or progress lines. Redesign constraints still pinned: avoid browser-native widgets, use a variety of fonts and colors, include animation, provide dark and light modes. Colour must not tint the surround of photos.

## Evidence on Hand
No real photos, logos or brand assets in the repo; tests generate synthetic JPEGs.

## Product Principles
1. Photos are the content; interface color stays out of their surround.
2. The keyboard is the primary input; every custom control stays keyboard-operable.
3. Nothing a user decided is ever lost or overwritten.
4. Fully usable offline and before indexing finishes.

## Accessibility & Inclusion
Custom controls keep real button/input semantics and ARIA roles; honour `prefers-reduced-motion`; both themes meet readable contrast.
