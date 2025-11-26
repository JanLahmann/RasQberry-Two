import RedirectClient from './RedirectClient';

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
