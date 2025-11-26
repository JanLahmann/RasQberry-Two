'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

type Stream = 'stable' | 'beta' | 'dev';

interface StreamData {
  tag: string;
  name: string;
  image_url: string;
  release_url: string;
  release_date: string;
  image_download_size: number;
  extract_size: number;
  extract_sha256: string;
}

interface ReleasesData {
  generated: string;
  streams: {
    [key: string]: StreamData;
  };
}

export default function LatestRedirect() {
  const params = useParams();
  const stream = params.stream as string;
  const [status, setStatus] = useState<'loading' | 'redirecting' | 'error'>('loading');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function redirect() {
      try {
        // Fetch the releases JSON
        const response = await fetch('/RQB-releases.json');
        if (!response.ok) {
          throw new Error('Failed to fetch release information');
        }

        const data: ReleasesData = await response.json();

        // Map URL param to stream key
        const streamKey = stream === 'stable' ? 'stable' : stream;

        if (!data.streams[streamKey]) {
          throw new Error(`No release found for stream: ${stream}`);
        }

        const streamData = data.streams[streamKey];
        setStatus('redirecting');

        // Redirect to the image URL
        window.location.href = streamData.image_url;
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    }

    redirect();
  }, [stream]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '2rem',
      fontFamily: 'system-ui, sans-serif'
    }}>
      {status === 'loading' && (
        <>
          <h1>RasQberry Two - {stream}</h1>
          <p>Loading release information...</p>
        </>
      )}

      {status === 'redirecting' && (
        <>
          <h1>RasQberry Two - {stream}</h1>
          <p>Redirecting to download...</p>
          <p style={{ fontSize: '0.875rem', color: '#666' }}>
            If the download doesn&apos;t start automatically,{' '}
            <a href={`/RQB-releases.json`}>check the releases JSON</a>
          </p>
        </>
      )}

      {status === 'error' && (
        <>
          <h1>Error</h1>
          <p style={{ color: '#c00' }}>{error}</p>
          <p>
            Available streams: <strong>stable</strong>, <strong>beta</strong>, <strong>dev</strong>
          </p>
          <p style={{ marginTop: '1rem' }}>
            <a href="/">Back to home</a> |{' '}
            <a href="/RQB-releases.json">View releases JSON</a>
          </p>
        </>
      )}
    </div>
  );
}

// Generate static pages for each stream
export function generateStaticParams() {
  return [
    { stream: 'stable' },
    { stream: 'beta' },
    { stream: 'dev' },
  ];
}
