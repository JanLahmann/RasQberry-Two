/*
 * RasQberry: Qoffee-Maker kiosk auto-start.
 *
 * This file is mounted into the Qoffee-Maker Docker container at
 *   /home/jovyan/.jupyter/custom/custom.js
 * by qoffee-maker.sh. Classic Jupyter Notebook 6.x (the base image is
 * jupyter/base-notebook:notebook-6.4.5) loads custom.js on every notebook page.
 *
 * When qoffee.ipynb finishes loading we fire the 'simple-app:app-activate'
 * action that the bundled qoffeefrontend/app nbextension registers - the same
 * action the toolbar "rocket" button triggers. That switches the page into
 * Qoffee app mode: it hides all Jupyter chrome, restarts the kernel, runs all
 * cells, and shows only the coffee-ordering widgets (the outputs of cells
 * marked "### APP"). The presenter therefore gets a ready-to-use kiosk without
 * clicking anything.
 *
 * The nbextension registers its action asynchronously, so we poll briefly for
 * it after notebook_loaded and fire exactly once. If the action never appears
 * (a different notebook, or the extension disabled) we give up after the
 * timeout and leave the normal notebook UI untouched.
 */
require(['base/js/namespace', 'base/js/events'], function (Jupyter, events) {
    'use strict';

    var ACTION = 'simple-app:app-activate';
    var POLL_MS = 500;
    var MAX_TRIES = 40; // ~20s for the extension to register its action

    function activateOnce() {
        var tries = 0;
        var timer = setInterval(function () {
            tries += 1;
            var ready = Jupyter.actions &&
                typeof Jupyter.actions.exists === 'function' &&
                Jupyter.actions.exists(ACTION);
            if (ready) {
                clearInterval(timer);
                try {
                    Jupyter.actions.call(ACTION);
                    console.log('[RasQberry] Qoffee app mode activated');
                } catch (e) {
                    console.error('[RasQberry] Qoffee app-activate failed', e);
                }
            } else if (tries >= MAX_TRIES) {
                clearInterval(timer);
                console.warn('[RasQberry] Qoffee app-activate action not found; ' +
                    'leaving the notebook UI as-is');
            }
        }, POLL_MS);
    }

    // Only auto-activate for the Qoffee notebook, so opening any other notebook
    // in the same server keeps the normal Jupyter interface.
    function maybeActivate() {
        var name = (Jupyter.notebook && Jupyter.notebook.notebook_name) || '';
        if (name.toLowerCase().indexOf('qoffee') !== -1) {
            activateOnce();
        }
    }

    if (Jupyter.notebook && Jupyter.notebook._fully_loaded) {
        maybeActivate();
    } else {
        events.on('notebook_loaded.Notebook', maybeActivate);
    }
});
