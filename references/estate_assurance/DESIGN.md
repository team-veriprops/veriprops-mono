# Design System Strategy: The Sovereign Architectural Editorial

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Sovereign Curator."** 

In the high-stakes world of international real estate verification, we must move beyond the "app-like" aesthetic of common fintech. This system adopts an editorial, architectural approach—mimicking the physical sensation of reviewing a high-end property portfolio or a legal deed. 

We reject the "boxed-in" layout of traditional dashboards. Instead, we embrace **Intentional Asymmetry** and **Tonal Depth**. By utilizing wide horizontal expanses of white space, staggered content blocks, and sophisticated typography scales, we create an environment that feels authoritative and bespoke. This design system bridges the gap between the speed of the diaspora’s digital life (UK/US/EU) and the grounded, tactile reality of Nigerian property investment.

---

## 2. Color & Atmosphere
This palette is designed to evoke the "Dark Navy" of a legal seal and the "Forest Green" of flourishing land.

### Tonal Foundations
- **Primary (`#000d22`):** Our "Midnight." Use this for high-impact text and foundational backgrounds to project absolute security.
- **Secondary (`#3f6653`):** Our "Veridian." Represents growth and the physical land. Use it for "Verified" states and growth-related metrics.
- **Tertiary (`#735c00`):** Our "Gold Leaf." Reserved for "Premium" tiers and high-value certification badges.

### The "No-Line" Rule
Traditional 1px borders are prohibited for sectioning. They create visual noise and feel "cheap." 
- **Method:** Define boundaries through **Background Shifts**. A `surface-container-low` (`#f3f4f5`) section should sit adjacent to a `surface` (`#f8f9fa`) area to create a clean, modern edge.

### The Glass & Gradient Rule
To achieve "High-End" polish, avoid flat primary colors for large CTAs.
- Use a subtle linear gradient transitioning from `primary` (`#000d22`) to `primary_container` (`#0a2342`) at a 135-degree angle. This adds "soul" and depth to buttons and hero headers.
- **Glassmorphism:** For floating modals or "Trust Score" overlays, use `surface_container_lowest` at 80% opacity with a `24px` backdrop-blur to maintain context and luxury.

---

## 3. Typography: The Editorial Voice
We use a dual-font strategy to balance architectural strength with digital clarity.

- **Display & Headlines (Manrope):** Chosen for its geometric precision. Use `display-lg` (3.5rem) with `-0.02em` letter spacing for hero headlines. This creates a "monumental" feel.
- **Body & Labels (Inter):** Chosen for its legendary legibility. All body text should use a generous line height (1.6 for `body-lg`) to ensure the Diaspora user feels a sense of "calm" while navigating complex data.
- **Hierarchy as Identity:** Use high contrast. A `display-sm` headline should be paired directly with a `label-md` uppercase sub-header in `secondary` to create an authoritative, "certified" look.

---

## 4. Elevation & Depth: Tonal Layering
We do not use structural lines. We use physics-based layering.

- **The Layering Principle:** 
    1. Base: `surface`
    2. Section: `surface-container-low`
    3. Cards: `surface-container-lowest` (White)
    This creates a "natural lift" that feels architectural.
- **Ambient Shadows:** When an element must float (e.g., a Tier Card), use a shadow: `0px 24px 48px rgba(0, 13, 34, 0.06)`. This uses the `on_surface` color for the shadow tint, mimicking natural light.
- **The "Ghost Border":** For input fields or accessibility, use `outline_variant` at **15% opacity**. It should be felt, not seen.

---

## 5. Signature Components

### Primary Actions (Buttons)
- **Style:** `0.375rem` (md) corner radius. 
- **Treatment:** Use the Signature Gradient (`primary` to `primary_container`). 
- **Padding:** 16px vertical / 32px horizontal. A wider button communicates confidence.

### Tier Comparison Cards
- **Structure:** Avoid vertical dividers. Use `surface_container_highest` for the "Standard" (middle) card to make it visually recede or pop against `surface_container_lowest`.
- **The "Premium" Card:** Use a subtle `outline` in `tertiary_fixed` (`#ffe088`) at 20% opacity to denote exclusivity.

### Status Trackers (Verification Steppers)
- **Aesthetic:** Horizontal, thin lines using `secondary_fixed` for completed states.
- **Indicator:** Use a "Pulse" effect on the active step—a semi-transparent `secondary_container` ring around the node.

### Trust Score Badges
- **Design:** Circular geometry. Use `secondary` for the score ring. 
- **Detail:** Incorporate a "Micro-Texture"—a very subtle 5% opacity "Security Pattern" (diagonal lines) within the badge background to suggest anti-counterfeit measures.

### Cards & Lists
- **Rule:** Absolute prohibition of 1px dividers.
- **Separation:** Use `32px` vertical spacing between list items. Use a `surface-container-low` background on hover to define the selection.

---

## 6. Do’s and Don’ts

### Do:
- **Use "White Space" as a Component:** Treat empty space as a functional element that guides the eye toward the "Verified" status.
- **Nester Surfaces:** Place `surface_container_highest` elements inside `surface_container_low` sections to create focal points.
- **Align to a 12-column Grid, then Break it:** Allow "Trust Badges" or "Certification Seals" to bleed slightly outside of the main content column to create an organic, high-end editorial feel.

### Don’t:
- **Never use Pure Black (#000000):** Use our `primary` (#000d22) for all deep tones to maintain the navy professional soul.
- **No Sharp Corners:** Avoid `radius: none`. Even at its most "professional," real estate is about homes and land; use `0.25rem` (DEFAULT) as the minimum to keep the UI approachable.
- **Avoid "Heavy" Borders:** High-contrast borders make the platform look like a legacy banking app. Stick to tonal shifts for a modern, global aesthetic.