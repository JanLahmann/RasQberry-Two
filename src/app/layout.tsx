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

export default function RootLayout({
  children
}: Readonly<Props>) {
  return (
    <html lang="en">
      <body className={plex.className}>
        {children}
        <Footer />
        <Script
          id="sender-net-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              window.addEventListener("onSenderFormsLoaded", function() {
                if (typeof senderForms !== 'undefined') {
                  senderForms.render();
                }
              });
            `,
          }}
        />
        <Script
          id="sender-net"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function (s, e, n, d, er) {
                s['Sender'] = er;
                s[er] = s[er] || function () {
                  (s[er].q = s[er].q || []).push(arguments)
                }, s[er].l = 1 * new Date();
                var a = e.createElement(n),
                    m = e.getElementsByTagName(n)[0];
                a.async = 1;
                a.src = d;
                m.parentNode.insertBefore(a, m)
              })(window, document, 'script', 'https://cdn.sender.net/accounts_resources/universal.js?explicit=true', 'sender');
              sender('a1da5edc354454')
            `,
          }}
        />
      </body>
    </html>
  );
}
