import type { Metadata } from 'next';
import RedirectClient from './RedirectClient';

// Redirects to the image file: nothing to index
export const metadata: Metadata = {
  title: 'Downloading RasQberry Two',
  robots: { index: false },
};

interface PageProps {
  params: {
    stream: string;
  };
}

export default function LatestRedirectPage({ params }: PageProps) {
  return <RedirectClient stream={params.stream} />;
}

// Generate static pages for each stream
export function generateStaticParams() {
  return [
    { stream: 'stable' },
    { stream: 'beta' },
    { stream: 'dev' },
  ];
}
