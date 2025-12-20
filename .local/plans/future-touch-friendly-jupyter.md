# Future Enhancement: Touch-Friendly Jupyter

## Background

There's no official touch-friendly Jupyter theme. The [JupyterLab mobile-friendly issue #3275](https://github.com/jupyterlab/jupyterlab/issues/3275) has been open since 2017 with 47+ upvotes but no native solution.

**RasQberry uses BOTH interfaces:**
- **JupyterLab** - Quantum Paradoxes notebooks (launched via `jupyter-lab`)
- **Jupyter Notebook classic** - Fun-with-Quantum notebooks (launched via `jupyter notebook`)

Both need touch-friendly CSS support.

## Problems with Default Jupyter on Touch Screens

| Problem | Impact |
|---------|--------|
| Tiny toolbar buttons | Hard to tap accurately |
| Narrow cell margins | Difficult to select cells |
| Small "+" add cell button | Easy to miss |
| Tiny scrollbars in output | Hard to grab |
| Small menu items | Frustrating navigation |
| Cell drag handles too small | Can't reorder cells easily |
| Code completion popups tiny | Hard to select suggestions |

## Proposed Solution

Create separate CSS files for each interface and apply when touch mode enabled:
- **JupyterLab**: `~/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings` + custom CSS
- **Jupyter Notebook**: `~/.jupyter/custom/custom.css`

### CSS File: `RQB2-config/touch-mode/jupyter-touch.css`

```css
/* RasQberry Touch-Friendly Jupyter CSS */
/* Material Design: 48px minimum touch targets */

/* Larger toolbar buttons */
.jp-Toolbar-item button,
.jp-ToolbarButtonComponent {
    min-height: 44px !important;
    min-width: 44px !important;
    padding: 8px !important;
}

/* Larger cell margins for selection */
.jp-Cell {
    margin: 8px 0 !important;
    padding: 12px !important;
}

/* Larger cell prompt (In [1]: area) */
.jp-InputPrompt,
.jp-OutputPrompt {
    min-width: 80px !important;
    padding: 12px !important;
}

/* Wider scrollbars */
.jp-OutputArea-output::-webkit-scrollbar,
.jp-CodeCell-input::-webkit-scrollbar {
    width: 16px !important;
    height: 16px !important;
}

.jp-OutputArea-output::-webkit-scrollbar-thumb,
.jp-CodeCell-input::-webkit-scrollbar-thumb {
    min-height: 48px !important;
}

/* Larger add cell button */
.jp-Notebook-footer button {
    min-height: 48px !important;
    font-size: 18px !important;
    padding: 12px 24px !important;
}

/* Larger menu items */
.lm-Menu-itemLabel {
    padding: 12px 16px !important;
    font-size: 16px !important;
}

.lm-Menu-item {
    min-height: 44px !important;
}

/* Larger tabs */
.lm-TabBar-tab {
    min-height: 44px !important;
    padding: 8px 16px !important;
}

/* Larger file browser items */
.jp-DirListing-item {
    min-height: 40px !important;
    padding: 8px !important;
}

/* Larger sidebar buttons */
.jp-SideBar button {
    min-height: 48px !important;
    min-width: 48px !important;
}

/* Larger kernel status indicator */
.jp-Notebook-ExecutionIndicator {
    min-width: 40px !important;
    min-height: 40px !important;
}

/* Autocomplete/completion menu */
.jp-Completer {
    font-size: 14px !important;
}

.jp-Completer-item {
    min-height: 36px !important;
    padding: 8px 12px !important;
}
```

## Implementation in `rq_touch_mode.sh`

### Variables (add at top):
```bash
JUPYTER_CUSTOM_DIR="$USER_HOME/.jupyter/custom"
JUPYTER_TOUCH_CSS_SRC="/usr/config/touch-mode/jupyter-touch.css"
```

### Enable (add in enable_touch_mode):
```bash
# Apply touch-friendly Jupyter CSS
if [ -f "$JUPYTER_TOUCH_CSS_SRC" ]; then
    mkdir -p "$JUPYTER_CUSTOM_DIR"
    if [ -f "$JUPYTER_CUSTOM_DIR/custom.css" ] && [ ! -f "$JUPYTER_CUSTOM_DIR/custom.css.touch-backup" ]; then
        cp "$JUPYTER_CUSTOM_DIR/custom.css" "$JUPYTER_CUSTOM_DIR/custom.css.touch-backup"
    fi
    cp "$JUPYTER_TOUCH_CSS_SRC" "$JUPYTER_CUSTOM_DIR/custom.css"
    info "Jupyter touch CSS applied"
fi
```

### Disable (add in disable_touch_mode):
```bash
# Restore Jupyter CSS
if [ -f "$JUPYTER_CUSTOM_DIR/custom.css.touch-backup" ]; then
    cp "$JUPYTER_CUSTOM_DIR/custom.css.touch-backup" "$JUPYTER_CUSTOM_DIR/custom.css"
    info "Jupyter CSS restored from backup"
elif [ -f "$JUPYTER_CUSTOM_DIR/custom.css" ]; then
    rm -f "$JUPYTER_CUSTOM_DIR/custom.css"
    info "Jupyter touch CSS removed"
fi
```

## Files to Create/Modify

1. **New:** `RQB2-config/touch-mode/jupyter-touch.css`
2. **Modify:** `RQB2-bin/rq_touch_mode.sh`
3. **Modify:** `RQB2-config/rasqberry_environment.env` (optional: add TOUCH_JUPYTER_ENABLED flag)

## Testing

1. Enable touch mode
2. Launch Jupyter: `jupyter lab` or `jupyter notebook`
3. Verify toolbar buttons are larger
4. Verify cells have more padding
5. Verify scrollbars are wider
6. Disable touch mode
7. Verify CSS removed/restored

## Notes

- Requires `--custom-css` flag for Jupyter Notebook 7+
- JupyterLab loads custom.css automatically
- May need to restart Jupyter after enabling touch mode
- CSS uses `!important` to override theme defaults

## References

- [JupyterLab mobile-friendly issue #3275](https://github.com/jupyterlab/jupyterlab/issues/3275)
- [Jupyter Notebook Custom CSS](https://jupyter-notebook.readthedocs.io/en/stable/custom_css.html)
- [JupyterLab CSS Patterns](https://jupyterlab.readthedocs.io/en/stable/developer/css.html)
- [JupyterLab Interface Customization](https://jupyterlab.readthedocs.io/en/latest/user/interface_customization.html)
