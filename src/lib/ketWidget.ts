'use client'

import { useEffect, useState } from "react";

// The FwQ widget (div#fwq-assistant, open shadow root) adds window.fwqAssistantOpen
// with FwQ PR #201; until then, press the widget's own floating button.
declare global {
    interface Window { fwqAssistantOpen?: () => void }
}

function widgetHost() {
    return document.getElementById('fwq-assistant');
}

/** Opens Ket's panel on this page, unless it is open already. */
export function openKet() {
    const button = widgetHost()?.shadowRoot?.querySelector<HTMLButtonElement>('.fa-open');
    if (button?.getAttribute('aria-expanded') === 'true') return;
    if (typeof window.fwqAssistantOpen === 'function') window.fwqAssistantOpen();
    else button?.click();
}

/** True once the widget is on the page: Ket entry points show only then. */
export function useKetReady() {
    const [ready, setReady] = useState(false);
    useEffect(() => {
        // The host only: its shadow content may be filled after it is added
        if (widgetHost()) { setReady(true); return; }
        const observer = new MutationObserver(() => { if (widgetHost()) { setReady(true); observer.disconnect(); } });
        observer.observe(document.body, { childList: true });
        return () => observer.disconnect();
    }, []);
    return ready;
}
