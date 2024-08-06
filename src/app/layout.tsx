import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";

import "@/styles/globals.scss";

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
      </body>
    </html>
  );
}
