# Graphite Rhythm

A compact desktop system for Hyprland, Waybar, Fuzzel, Mako, Hyprlock and Alacritty.
Implemented 2026-10-16. Physical review: DP-1, 1920×1080, scale 1.

## Design principle

A continuous graphite plane, warm readable typography, and a single gold focus signal.
Mauve identifies secondary information. Alignment and density carry the composition;
there are no decorative exterior gaps, rounded cards, shadows or blur.
Native Adwaita dark application widgets and Paper icons retain their existing identity.
Their toolkit geometry is intentionally not overridden by broad user CSS.

## Geometry

The base unit u is 4 logical pixels. A 2px optical half-step is available for compact
controls; 1px is reserved for internal dividers and passive popup outlines.

| Role | Value | Relationship / purpose |
| --- | --- | --- |
| Exterior gaps, radii | 0 | Continuous rectangular composition |
| Internal divider / passive popup outline | 1px | Hairline; less prominent than focus |
| Window / launcher / lock outline | 2px | Half-unit; visible without a heavy frame |
| Small interval | 4px | 1u; menu container inset |
| Compact horizontal inset | 6px | 1.5u; two neighboring modules give a 12px interval |
| Small content inset / tray separation | 8px | 2u |
| Normal content inset | 12px | 3u |
| Large content inset / panel icon | 16px | 4u |
| Panel / launcher row | 28px | 7u; compact desktop row |
| Notification icon maximum | 32px | 8u; does not dominate a short notification |
| Lock input | 320×48px | 80u × 12u; intentional larger authentication target |
| Lock time / layout center offsets | +120 / −64px | 30u / −16u; hierarchy around the centered input |
| Notification width | 360px | 90u; retained readable line measure |
| Review floating window | 640×400px | Review fixture only, not a new application rule |

Waybar remains 28px tall, edge to edge. Workspace targets are now 28×28px,
including padding (previously 30px wide). The title begins after a 1px divider
and 12px inset. Status modules retain the user's compact 6px horizontal inset.
The clock has 12px horizontal breathing room. Tray icons are 16px with 8px separation.

Fuzzel uses 16px horizontal / 12px vertical padding and an 8px prompt/list interval.
Its native line-height value is **21**, yielding a measured 28px row at 96 DPI.
`dpi-aware=no` keeps it on compositor scale like the other components, avoiding
physical-DPI differences. Eight rows plus the prompt preserve the existing workflow.
Width stays at 48 estimated characters; forcing proportional text onto a fixed pixel
width would be less useful than retaining the readable line measure.

Mako uses 12px vertical / 16px horizontal content padding. It remains flush against
the screen edge beneath the panel. Alacritty uses a minimum 8px inset on each axis;
`dynamic_padding=true` distributes leftover character-cell pixels optically.

## Typography

Iosevka Aile is the interface family; IosevkaTerm Nerd Font Mono is the reading and
calendar family; Nerd Font Propo provides panel icons without compressed mono cells.

| Role | Size | Weight |
| --- | --- | --- |
| Compact panel, tooltip, tray menu | 14px | Regular; bold only occupied/active workspace and clock time |
| System UI, launcher, notification, lock layout | 11pt | Regular; notification heading uses native bold |
| Terminal reading | 13pt | Regular; native bold/italic preserved |
| Panel icons | 12pt = 16px at 96 DPI | Proportional Nerd glyphs |
| Lock clock | 40pt | Display hierarchy |

The compact/body/reading sequence approximates a gentle 7:8 modular progression,
rounded to native toolkit units. The panel's 14px text is optically smaller than
11pt body text (14.67px at 96 DPI); they are deliberately not treated as equal.
Terminal size 13pt is the existing user reading preference and is preserved.
Pango icon markup uses 12288 units (12×1024), replacing the approximate 12000.
No letter-spacing correction is applied to a family already designed for UI rhythm.

## Color roles

| Role | Hex | Use |
| --- | --- | --- |
| Base | #282828 | Panel, launcher, notifications, lock, terminal |
| Occupied surface | #323230 | Occupied workspace; lock input |
| Hover surface | #353432 | Pointer feedback |
| Passive edge | #504945 | Inactive window, popup border, divider |
| Primary text | #d4c7ad | Main text |
| Secondary text | #a89984 | Empty workspace, title, date, muted audio |
| Focus | #c1a16b | Active border/workspace, selection |
| Healthy connection | #a3a878 | Connected network icon |
| Secondary accent | #b3919e | Keyboard layout |
| Alert | #d39a8b | Urgent workspace, failed authentication, critical notification |
| Caution | #c1a16b | Caps Lock |

Window focus is solid gold rather than a two-accent gradient: mauve now keeps a
consistent secondary role. Selections use graphite text on gold. The occupied
workspace remains a restrained surface, subordinate to the active workspace.
Terminal ANSI colors and cursor are retained: their established semantic roles
must not be conflated with the shell's focus/selection roles.

Contrast figures are recorded in the review report. Passive edges intentionally
have low contrast; they carry structure and are not the sole state indicator.

## Implementation and review

Configurations are native component files; there is no theme daemon, generated
runtime config, or new startup dependency. This document is the shared specification;
comments in edited files link here. Future changes should update the role in this
specification and its component mappings together.

Changed files:
- ~/.config/hypr/hyprland.lua
- ~/.config/waybar/style.css and config.jsonc
- ~/.config/fuzzel/fuzzel.ini
- ~/.config/mako/config
- ~/.config/hypr/hyprlock.conf
- ~/.config/alacritty/alacritty.toml

Evidence and guarded restore:
~/.local/state/theme-backups/20261016-design-system/RESULT.md
~/.local/state/theme-backups/20261016-design-system/restore.py

Live panel, real launcher and notification screenshots were reviewed, including
two tiled windows and a floating window. Workspace 2 was restored and test windows
were closed. The actual lock screen/PAM cycle is untested; its config changes will
appear at the next ordinary lock. No greetd restart or greeter changes were made.
GTK/Qt widget geometry, multi-monitor scaling and touch ugold were not validated.
No dotfiles publication or ISO rebuild is included in this local desktop change.
