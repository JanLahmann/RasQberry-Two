// Ket, the RasQberry helper (Fun with Quantum's assistant), is open to every
// visitor until this moment, the end of Jan 31, 2027 (Jan, 16 Nov 2026: "until Jan 31, 2027
// for now"). Afterwards it loads only where it did before: ?assistant=1, a Pi
// (?from=pi; "device" context), or a page with [data-fwq-assistant] (testing).
// Elsewhere no request goes to its server (privacy page).
export const KET_OPEN_UNTIL = "2027-02-01T00:00:00+01:00";

// Inline loader for the end of <body> (no backslashes: the build turned "\\b"
// into a backspace). data-public="1" lets the widget open without ?assistant=1.
export function ketLoader(openUntil = KET_OPEN_UNTIL) {
  const until = Date.parse(openUntil);
  return `(function(){try{var q=new URLSearchParams(location.search),s=sessionStorage,o=Date.now()<${until};` +
    `if(!(o||q.get("assistant")==="1"||q.get("from")==="pi"||s.getItem("fwq-assistant")||s.getItem("fwq-from-pi")` +
    `||s.getItem("rq-from")==="pi"||document.querySelector("[data-fwq-assistant]")))return;` +
    `var e=document.createElement("script");e.defer=true;e.src="https://fwq-assistant.jan-35c.workers.dev/widget.js";` +
    `e.setAttribute("data-site","rasqberry");e.setAttribute("data-context","build");` +
    `e.setAttribute("data-context-pi","device");if(o)e.setAttribute("data-public","1");` +
    `document.body.appendChild(e)}catch(e){}})()`;
}
