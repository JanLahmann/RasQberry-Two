import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Latest RasQberry Two images",
  description: "Download the newest RasQberry Two SD card images: stable, beta and development releases, each with its highlights.",
  alternates: { canonical: "/latest/" },
};

export default function LatestLayout({ children }: { children: React.ReactNode }) {
  return children;
}
