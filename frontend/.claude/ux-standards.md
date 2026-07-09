# UX Standards Reference

## UI Clarity & Interaction Standards

Design every interface for immediate comprehension, discoverability, and confident interaction.

### Guidance & Context

All non-obvious or interactive UI elements should clearly communicate intent using appropriate combinations of: tooltips, labels, helper text, inline descriptions, placeholders/examples, empty states, status indicators, loading/success/error feedback, progressive disclosure.

### Tooltip Rules

Add tooltips to: icon-only actions, ambiguous controls, technical terminology, truncated content, disabled actions, advanced settings, metrics/KPIs/charts, status badges, keyboard shortcuts.

Tooltips must be concise, explain purpose or consequence (not just labels), avoid duplicating visible text, and use plain language over jargon.

### Feedback & System States

Important actions must provide clear loading states, success/error feedback, visible outcome confirmation, and recovery guidance on failure.

### Forms & Validation

All form inputs should include clear labels, helpful examples/placeholders, validation guidance, and human-readable error messages that explain what failed, why, and how to fix it.

### Empty & Edge States

Empty states should explain why content is missing, suggest the next action, and reduce uncertainty. Edge cases and failures must never leave users stranded.

### Data & Dashboard UX

Use tooltips/help text for KPIs, calculations, aggregations, and financial/statistical terminology. Dense interfaces should use visual hierarchy, logical grouping, expand/collapse patterns, and progressive disclosure.

### AI & Automation UX

AI-generated results should clearly communicate what was generated, confidence/limitations where relevant, recommended next actions, and whether human review is advised.

---

## Cursor & Interactive Element Standards

### Required Cursor Behavior

- Clickable elements → `cursor-pointer`
- Text inputs/textareas → `cursor-text`
- Drag interactions → `cursor-grab` / `cursor-grabbing`
- Disabled actions → `cursor-not-allowed`
- Loading states → `cursor-wait` where appropriate

Never leave clickable elements with default cursor behavior.

### Interaction Requirements

Every interactive element must provide: hover states, focus-visible states, keyboard accessibility, clear interaction feedback, consistent desktop/mobile behavior. Do not rely solely on color for interaction feedback.

### Accessibility

Focus-visible styling is mandatory. Disabled and loading states must be visually distinct. All interactive affordances must remain clear for mouse, keyboard, and touch users.

---

## PR / Review Checklist

Before completing any UI work, verify:

- Interactive elements look interactive (cursor, hover, focus states present)
- Disabled states are distinguishable; loading states communicate progress
- Empty/error states provide guidance
- Complex actions include contextual help
- Mobile and desktop interactions remain consistent
