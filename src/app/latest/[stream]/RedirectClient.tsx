'use client';

import { useEffect, useState } from 'react';

interface StreamData {
  tag: string | null;
  name: string | null;
  image_url?: string;
  release_url: string;
  release_date?: string;
  image_download_size?: number;
  extract_size?: number;
  extract_sha256?: string;
  message?: string;
}

interface ReleasesData {
  generated: string;
  streams: {
    [key: string]: StreamData;
  };
}

interface RedirectClientProps {
  stream: string;
}

export default function RedirectClient({ stream }: RedirectClientProps) {
  const [status, setStatus] = useState<'loading' | 'redirecting' | 'unavailable' | 'error'>('loading');
  const [error, setError] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [releaseUrl, setReleaseUrl] = useState<string>('');

  useEffect(() => {
    async function redirect() {
      try {
        // Fetch the releases JSON
        const response = await fetch('/RQB-releases.json');
        if (!response.ok) {
          throw new Error('Failed to fetch release information');
        }

        const data: ReleasesData = await response.json();

        if (!data.streams[stream]) {
          throw new Error(`No release found for stream: ${stream}`);
        }

        const streamData = data.streams[stream];

        // Check if stream has an image URL (i.e., has an actual release)
        if (!streamData.image_url || !streamData.tag) {
          // No release available for this stream
          setStatus('unavailable');
          setMessage(streamData.message || `No ${stream} release available yet.`);
          setReleaseUrl(streamData.release_url || 'https://github.com/JanLahmann/RasQberry-Two/releases');
          return;
        }

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

      {status === 'unavailable' && (
        <>
          <h1>RasQberry Two - {stream}</h1>
          <p style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>{message}</p>
          <p>
            <a href="/latest/beta" style={{ marginRight: '1rem' }}>Download Beta</a>
            <a href="/latest/dev">Download Dev</a>
          </p>
          <p style={{ marginTop: '2rem', fontSize: '0.875rem', color: '#666' }}>
            <a href="/">Back to home</a> |{' '}
            <a href={releaseUrl}>View all releases</a>
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
