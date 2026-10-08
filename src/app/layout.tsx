import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import Script from "next/script";

import "@/styles/globals.scss";
import { Footer } from "@/components/Footer";

const plex = IBM_Plex_Sans({ weight: ['100', '200', '300', '400', '500', '600', '700'], subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RasQberry Two",
  description: "Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer",
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

export default function RootLayout({
  children
}: Readonly<Props>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: FROM_PI }} />
      </head>
      <body className={plex.className}>
        {children}
        <Footer />
        <Script
          defer
          src="https://cloud.umami.is/script.js"
          data-website-id="97f347ac-e7ba-4be3-b26f-ab4b328bdbf2"
          data-domains="rasqberry.org"
        />
      </body>
    </html>
  );
}
