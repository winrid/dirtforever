# DirtForever Web Style Guide

## Borders

**NO standalone borders on cards, tiles, or UI components.** A card either has a uniform border on ALL sides or NO border at all. Never apply `border-top`, `border-left`, `border-right`, or `border-bottom` individually as a decorative accent.

Use background tints, box-shadows, or opacity changes for emphasis instead.

## Text Contrast

All text must be high contrast against its background. No light grey text. Every piece of text on the page must be clearly readable without straining.

- Primary text: `--text` (#E8E4DF)
- Secondary text: `--text-muted` (#B0AFB8) — minimum acceptable contrast
- Tertiary text: `--text-dim` (#8A8992) — use sparingly, still must be readable

## Rendering

All pages are server-side rendered via Flask + Jinja2. No SPA patterns. JavaScript is for progressive enhancement only (animations, counters, form filtering) — never for routing or content rendering.
