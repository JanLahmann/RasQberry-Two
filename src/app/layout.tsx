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
          defer
          src="https://cloud.umami.is/script.js"
          data-website-id="97f347ac-e7ba-4be3-b26f-ab4b328bdbf2"
          data-domains="rasqberry.org"
        />
      </body>
    </html>
  );
}
