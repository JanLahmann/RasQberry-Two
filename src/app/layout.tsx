import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import Script from "next/script";

import "@/styles/globals.scss";
import { OG_IMAGE } from "@/utils/pageMeta";
import { Footer } from "@/components/Footer";

const plex = IBM_Plex_Sans({ weight: ['100', '200', '300', '400', '500', '600', '700'], subsets: ["latin"] });

// Defaults; content pages set their own title, description and canonical
export const metadata: Metadata = {
  metadataBase: new URL("https://rasqberry.org"),
  title: { default: "RasQberry Two", template: "%s" },
  description: "Build a functional model of a quantum computer at home: a 3D-printed IBM Quantum System Two with a Raspberry Pi, LEDs, Qiskit and quantum demos.",
  openGraph: {
    type: "website",
    siteName: "RasQberry Two",
    images: [OG_IMAGE],
  },
  twitter: { card: "summary_large_image", images: [OG_IMAGE.url] },
};

interface Props {
  children: React.ReactNode;
}

// The Pi opens rasqberry.org/?from=pi (its start page and Chromium's home
// page): mark the page before it is drawn, for the rest of the visit in this
// tab, so the homepage greets the Pi instead of offering to write the SD card
// it already runs from (.only-pi / .not-pi in globals.scss)
const FROM_PI = `try{var q=new URLSearchParams(location.search);` +
  `if(q.get("from")==="pi")sessionStorage.setItem("rq-from","pi");` +
  `if(sessionStorage.getItem("rq-from")==="pi")document.documentElement.setAttribute("data-from","pi")}catch(e){}`;

// Fun with Quantum's standard tracker filter (every family site): ?notrack
// keeps this browser out of the counts (?track undoes it), and headless
// browsers and bots send nothing (no backslashes in this string: the
// build turned "\\b" into a backspace). Pages opened on a Pi (?from=pi, see above)
// count as device.rasqberry.org, like the Pi's own events
// (rq_umami_event.py), so rasqberry.org shows only website visitors.
const UMAMI_FILTER = `(function(){try{var q=location.search;` +
  `if(/[?&]notrack(?=$|[&=])/.test(q))localStorage.setItem('umami.disabled','1');` +
  `if(/[?&]track(?=$|[&=])/.test(q))localStorage.removeItem('umami.disabled')}catch(e){}` +
  `window.fwqUmamiBeforeSend=function(t,p){var n=navigator;` +
  `if(n.webdriver||/HeadlessChrome|bot|crawl|spider|Lighthouse|PageSpeed/i.test(n.userAgent))return false;` +
  `try{if(sessionStorage.getItem("rq-from")==="pi"&&p)p.hostname="device.rasqberry.org"}catch(e){}` +
  `return p}})();`;

export default function RootLayout({
  children
}: Readonly<Props>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: FROM_PI }} />
        <script dangerouslySetInnerHTML={{ __html: UMAMI_FILTER }} />
      </head>
      <body className={plex.className}>
        {children}
        <Footer />
        <Script
          defer
          src="https://cloud.umami.is/script.js"
          data-website-id="97f347ac-e7ba-4be3-b26f-ab4b328bdbf2"
          data-domains="rasqberry.org"
          data-before-send="fwqUmamiBeforeSend"
        />
        {/* The RasQberry helper (Fun with Quantum's assistant): hidden until
            the URL has ?assistant=1; "device" context on the Pi (?from=pi) */}
        <Script
          defer
          src="https://fwq-assistant.jan-35c.workers.dev/widget.js"
          data-site="rasqberry"
          data-context="build"
          data-context-pi="device"
        />
      </body>
    </html>
  );
}
