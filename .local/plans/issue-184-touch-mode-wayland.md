# Issue #184: Improve Touch Mode for Wayland

## Summary

Enhance touch mode with three improvements focused on Wayland/labwc:
1. **Single-click to open** - Easy (libfm.conf change)
2. **Larger window decorations** - Moderate (labwc themerc-override)
3. **Long-press right-click** - Skip for now (complex, low ROI)

---

## 1. Single-Click Desktop Icons

**Change:** Set `single_click=1` in libfm.conf when touch mode enabled.

**Files:**
- `RQB2-bin/rq_touch_mode.sh`

**In `enable_touch_mode()` (after big_icon_size code ~line 186):**
```bash
# Enable single-click to open for touch-friendly desktop icons
if grep -q "^single_click=" "$LIBFM_CONFIG"; then
    sed -i "s/^single_click=.*/single_click=1/" "$LIBFM_CONFIG"
else
    if grep -q "^\[config\]" "$LIBFM_CONFIG"; then
        sed -i "/^\[config\]/a single_click=1" "$LIBFM_CONFIG"
    fi
fi
info "Single-click desktop icons enabled"
```

**In `disable_touch_mode()` (~line 328):**
```bash
# Restore double-click for desktop icons
if [ -f "$LIBFM_CONFIG" ]; then
    sed -i "s/^single_click=.*/single_click=0/" "$LIBFM_CONFIG"
    info "Double-click desktop icons restored"
fi
```

---

## 2. Larger Window Decorations (labwc)

**Approach:** Create `~/.config/labwc/themerc-override` with touch-friendly values.

### New Variables

**Add to top of `rq_touch_mode.sh` (~line 58):**
```bash
LABWC_CONFIG_DIR="$USER_HOME/.config/labwc"
LABWC_THEMERC_OVERRIDE="$LABWC_CONFIG_DIR/themerc-override"
```

**Add detection function (~line 70):**
```bash
is_labwc() {
    pgrep -x labwc >/dev/null 2>&1
}
```

**Add to `rasqberry_environment.env`:**
```bash
# Touch mode - labwc window decorations (Wayland)
TOUCH_LABWC_BUTTON_SIZE=40
TOUCH_LABWC_BORDER_WIDTH=6
TOUCH_LABWC_TITLEBAR_PADDING=6
```

### Enable Logic

**In `enable_touch_mode()` (after panel section ~line 158):**
```bash
# Update labwc window decorations (Wayland)
if is_labwc || [ -d "$LABWC_CONFIG_DIR" ]; then
    mkdir -p "$LABWC_CONFIG_DIR"
    if [ -f "$LABWC_THEMERC_OVERRIDE" ] && [ ! -f "${LABWC_THEMERC_OVERRIDE}.touch-backup" ]; then
        cp "$LABWC_THEMERC_OVERRIDE" "${LABWC_THEMERC_OVERRIDE}.touch-backup"
    fi

    cat > "$LABWC_THEMERC_OVERRIDE" << EOF
# RasQberry Touch Mode - larger window decorations
window.button.width: ${TOUCH_LABWC_BUTTON_SIZE:-40}
window.button.height: ${TOUCH_LABWC_BUTTON_SIZE:-40}
window.button.spacing: 4
window.titlebar.padding.width: 8
window.titlebar.padding.height: ${TOUCH_LABWC_TITLEBAR_PADDING:-6}
border.width: ${TOUCH_LABWC_BORDER_WIDTH:-6}
EOF

    # Signal labwc to reload
    pgrep -x labwc >/dev/null && pkill -HUP labwc 2>/dev/null || true
    info "labwc decorations enlarged (buttons=${TOUCH_LABWC_BUTTON_SIZE:-40}px)"
fi
```

### Disable Logic

**In `disable_touch_mode()` (~line 309):**
```bash
# Restore labwc window decorations
if [ -f "${LABWC_THEMERC_OVERRIDE}.touch-backup" ]; then
    cp "${LABWC_THEMERC_OVERRIDE}.touch-backup" "$LABWC_THEMERC_OVERRIDE"
    info "labwc themerc-override restored"
elif [ -f "$LABWC_THEMERC_OVERRIDE" ]; then
    rm -f "$LABWC_THEMERC_OVERRIDE"
    info "labwc themerc-override removed"
fi
pgrep -x labwc >/dev/null && pkill -HUP labwc 2>/dev/null || true
```

### Update Status Display

Add to `show_status()`:
```bash
if [ -f "$LABWC_THEMERC_OVERRIDE" ]; then
    echo "  labwc decorations: touch-friendly"
fi
```

---

## 3. Long-Press Right-Click

**Decision: SKIP** - Complexity outweighs benefit:
- Requires additional packages (ydotool) and daemon
- No native Wayland gesture support
- Single-click mode reduces need for right-click
- Can revisit if users request it

---

## Touch-Friendly Values Reference

| Element | Default | Touch Value |
|---------|---------|-------------|
| Window buttons | 26px | 40px |
| Window border | 1px | 6px |
| Titlebar padding | 0px | 6px |
| Desktop icons | 48px | 72px |
| GTK buttons | varies | 48px min |

---

## Files to Modify

1. `RQB2-bin/rq_touch_mode.sh` - Add single-click + labwc support
2. `RQB2-config/rasqberry_environment.env` - Add labwc size variables

---

## Testing

1. Enable touch mode on labwc session
2. Verify single-click opens desktop icons
3. Verify window buttons are larger (~40px)
4. Verify window borders are wider (~6px)
5. Disable touch mode
6. Verify all settings restored
