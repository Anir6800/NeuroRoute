# Stitch master design brief (Soft Liquid Minimal)

> **Provenance, please read.** The task said to paste a "provided master design prompt" into Stitch, but no such prompt text was supplied. This file therefore does **not** contain that original prompt. It contains the design brief exactly as stored in the existing Stitch project **"AI Network Design System"** (`projects/11953126075048924226`, created 2026-10-21), copied verbatim from its design system (`designTheme.designMd`). That is the approved source for `design/tokens.json`.
>
> If you have the original master prompt, add it above this note. Two separate Stitch projects (NeuroRoute indigo, NetMind teal) have **not** been created; the existing project covers both "tenants".
>
> Known inconsistency in the source: the YAML `rounded` scale (`md` 0.75rem, `lg` 1rem, `xl` 1.5rem) disagrees with the "Shapes" prose (8 / 12 / 16 px). `tokens.json` follows the prose.

---

---
name: Soft Liquid Minimal
colors:
  surface: '#0f131b'
  surface-dim: '#0f131b'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#c6c5d4'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#908f9e'
  outline-variant: '#454652'
  surface-tint: '#bdc2ff'
  primary: '#bdc2ff'
  on-primary: '#152188'
  primary-container: '#7d88ee'
  on-primary-container: '#0b1781'
  inverse-primary: '#4954b7'
  secondary: '#64d9d0'
  on-secondary: '#003734'
  secondary-container: '#17a199'
  on-secondary-container: '#00302d'
  tertiary: '#ffba50'
  on-tertiary: '#452b00'
  tertiary-container: '#c1851d'
  on-tertiary-container: '#3c2500'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dfe0ff'
  primary-fixed-dim: '#bdc2ff'
  on-primary-fixed: '#000866'
  on-primary-fixed-variant: '#303b9e'
  secondary-fixed: '#82f5ec'
  secondary-fixed-dim: '#64d9d0'
  on-secondary-fixed: '#00201e'
  on-secondary-fixed-variant: '#00504b'
  tertiary-fixed: '#ffddb3'
  tertiary-fixed-dim: '#ffba50'
  on-tertiary-fixed: '#291800'
  on-tertiary-fixed-variant: '#624000'
  background: '#0f131b'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.025em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  code-lg:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.01em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0.01em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.08em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.5rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 3rem
---

## Brand & Style

This design system establishes a high-precision, dual-tenant environment engineered for local-first AI networking tools. The system bridges two core operational modes:
- **Academic & Research Topology Engine**: Analytical, exploratory, long-horizon modeling, and research-grade pipeline visualization.
- **Advanced Telemetry & Network Operations**: High-density throughput monitoring, dynamic routing control planes, and fault isolation.

The aesthetic follows a **Soft Liquid Minimal** framework. Rather than relying on hyper-saturated cyberpunk tropes or overwhelming sci-fi visual noise, it prioritizes clarity, structural serenity, and dense data legibility. Surfaces are treated like fluid optical layers—frosted, semi-translucent, and structurally anchored by hairline borders. The visual tone is disciplined, academic, and calm under high incident load.

## Colors

The palette is engineered with dark mode as primary for dense telemetry environments, with a complete 1:1 parity light mode for academic documentation and daylight fieldwork.

### Dual Primary Identities
- **Academic Research**: Primary Indigo (`#6974D9`), accented by low-alpha atmospheric washes (`rgba(105, 116, 217, 0.08)` to `rgba(105, 116, 217, 0.16)`).
- **Telemetry & NetOps**: Primary Teal (`#0D9E96`), supported by focused telemetry halos (`rgba(13, 158, 150, 0.08)` to `rgba(13, 158, 150, 0.16)`).

### Canvas & Structural Neutrals
- **Dark Mode (Default)**:
  - Base Canvas: `#10141C`
  - Elevated Container / Surface: `#161B26`
  - Subtle Hairline Structural Borders: `#232B3A`
  - Interactive Hover Overlay: `rgba(255, 255, 255, 0.04)`
- **Light Mode**:
  - Base Canvas: `#F7F8FC`
  - Elevated Container / Surface: `#FFFFFF`
  - Subtle Hairline Structural Borders: `#E2E5F0`
  - Interactive Hover Overlay: `rgba(0, 0, 0, 0.03)`

### Semantic Telemetry Signals
- **Healthy / Resolved**: Emerald (`#10B981` default, `#059669` contrast anchor)
- **Warning / Degraded**: Amber (`#F59E0B` default, `#D97706` contrast anchor)
- **Critical / Packet Drop / Down**: Rose (`#EF4444` default, `#DC2626` contrast anchor)
- **Telemetry Stream / Discovery**: Cyan (`#0EA5E9`)

## Typography

The type scale strictly partitions semantic human language from machine output:
- **Inter** governs narrative UI, high-level headers, navigational primitives, and contextual operational guidance.
- **JetBrains Mono** governs all raw compute output: IP addresses, BGP autonomous system numbers, subnet masks, latencies, cryptographical hashes, node metrics, and raw terminal feeds.

Tabular figures (`tnum`) must remain enabled across both families to eliminate horizontal jitter during real-time metric streams.

## Layout & Spacing

A strict **8px baseline rhythm** rules density and alignments, scaling through atomic increments (4px, 8px, 12px, 16px, 24px, 32px, 48px).

### Layout Geometry
- **Desktop (>= 1280px)**: 12-column dynamic grid, 16px gutters, 24px canvas margins. High-density telemetry sidebars remain fixed at 280px or 320px, with internal node canvas views expanding infinitely via a fluid central viewport.
- **Tablet (768px - 1279px)**: 8-column layout, 16px gutters, 20px canvas margins. Inspector rails collapse into slide-over sheets.
- **Mobile (< 768px)**: 4-column layout, 8px gutters, 16px canvas margins. Multi-metric monitors collapse into vertical stacked micro-cards.

## Elevation & Depth

Visual hierarchy rejects exaggerated, pitch-black drop shadows in favor of **Soft Liquid Minimal** optical stacking:

### 1. Optical Backdrop Diffusion
All floating sheets, cards, tooltips, and top-level navigation bars utilize backdrop filtering:
- Dark Mode: `background: rgba(22, 27, 38, 0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);`
- Light Mode: `background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);`

### 2. Hairline Structural Outlines
Every elevated panel is bound by a unified 1px hairline boundary:
- Dark Mode: `1px solid #232B3A`
- Light Mode: `1px solid #E2E5F0`

### 3. Diffused Ambient Shadows
Shadows serve purely as ambient ground detachment rather than light-source simulations:
- Low-tier container: `0 2px 8px -1px rgba(0, 0, 0, 0.04)`
- High-tier floating panels / popovers: `0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 1px 3px 0 rgba(0, 0, 0, 0.03)`

## Shapes

The interface balances precision engineering with tactile softness. Corner radii conform strictly to three tiers:
- **8px (`rounded-md` / Buttons & Badges)**: Interactive targets, pills, segmented toggles, status pills, and small tooltips.
- **12px (`rounded-lg` / Core Surface & Inputs)**: Telemetry cards, configuration forms, terminal panels, graph nodes, and data table blocks.
- **16px (`rounded-xl` / Structural Overlays)**: Modal dialogs, floating context sheets, detached filter bars, and system command palettes.

## Components

Tailored for direct integration with shadcn/ui and Tailwind tokens.

### Buttons & Actions
- **Primary (NeuroRoute)**: Background `#6974D9`, text white, `rounded-md` (8px), height 36px (compact) or 40px (default). Active state: subtle scale down (`0.985`), transition `120ms ease-out`.
- **Primary (NetMind)**: Background `#0D9E96`, text white, same geometry and transitions.
- **Secondary / Ghost**: Translucent background (`rgba(255,255,255,0.03)` dark / `rgba(0,0,0,0.02)` light) with hairline border (`#232B3A` dark / `#E2E5F0` light).
- **Destructive**: Hairline border with Rose-alpha tint (`rgba(239, 68, 68, 0.15)`), text `#EF4444`.

### Telemetry Badges & Chips
- Compact heights (20px to 24px) with `rounded-md` (8px).
- Pair `code-sm` typography with a pulsing or solid 6px semantic LED dot (Emerald, Amber, Rose, Cyan).
- Transparent backgrounds with a 10% tint of the respective status color.

### Form Inputs & Network Fields
- Input fields use 12px radii, height 38px, font `body-md` (or `code-md` for IP/CIDR input).
- Background: Surface tier (`#161B26` dark, `#FFFFFF` light), border 1px solid.
- Focus: Hairline border shifts to brand primary (`#6974D9` or `#0D9E96`) accompanied by an ambient 2px outer ring with 20% alpha.

### Surface Cards & Inspector Panels
- Frosted glass backing with `backdrop-filter: blur(12px)`.
- Internal padding using `space-lg` (16px) or `space-xl` (24px).
- Panel headers feature a subtle bottom hairline border separation.

### Checkboxes, Radios & Switches
- Checkboxes: 16x16px, 4px corner radius, primary-filled when selected with a sharp white checkmark.
- Switches: Track width 36px, height 20px, pill-radii; thumb 16px with crisp diffused shadow.

### Real-Time Metric Tiles & Terminal Windows
- Monospace-dominant grid data rows with subtle alternating hovers (`rgba(255,255,255,0.02)`).
- Latency and throughput sparks are rendered with clean 1.5px paths, without heavy glowing drop-gradients.
- All live data updates respect `120ms - 180ms ease-out` CSS transitions.
