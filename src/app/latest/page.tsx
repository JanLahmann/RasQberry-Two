'use client';

import { useEffect, useState } from 'react';

interface StreamData {
  tag: string | null;
  name: string | null;
  image_url?: string;
  release_url: string;
  release_date?: string;
  image_download_size?: number;
  message?: string;
}

interface ReleasesData {
  generated: string;
  streams: {
    [key: string]: StreamData;
  };
}

const streamInfo = {
  stable: {
    title: 'Stable',
    subtitle: 'Recommended',
    description: 'Production-ready release for everyday use',
  },
  beta: {
    title: 'Beta',
    subtitle: 'Testing',
    description: 'New features for testing before stable release',
  },
  dev: {
    title: 'Development',
    subtitle: 'Unstable',
    description: 'Latest development build with cutting-edge features',
  },
};

function formatSize(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  return gb.toFixed(1) + ' GB';
}

export default function LatestPage() {
  const [releases, setReleases] = useState<ReleasesData | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function fetchReleases() {
      try {
        const response = await fetch('/RQB-releases.json');
        if (!response.ok) throw new Error('Failed to fetch releases');
        const data = await response.json();
        setReleases(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    }
    fetchReleases();
  }, []);

  const cardStyle: React.CSSProperties = {
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '1.5rem',
    marginBottom: '1rem',
    backgroundColor: '#fff',
  };

  const buttonStyle: React.CSSProperties = {
    display: 'inline-block',
    padding: '0.5rem 1rem',
    backgroundColor: '#0f62fe',
    color: '#fff',
    textDecoration: 'none',
    borderRadius: '4px',
    marginRight: '0.5rem',
  };

  const disabledButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    backgroundColor: '#c6c6c6',
    cursor: 'not-allowed',
  };

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      padding: '2rem',
      fontFamily: 'system-ui, sans-serif',
    }}>
      <h1 style={{ marginBottom: '0.5rem' }}>RasQberry Two Downloads</h1>
      <p style={{ color: '#666', marginBottom: '2rem' }}>
        Choose a release stream to download the RasQberry Two image.
      </p>

      {error && (
        <p style={{ color: '#c00' }}>Error loading releases: {error}</p>
      )}

      {!releases && !error && <p>Loading releases...</p>}

      {releases && (
        <>
          {(['stable', 'beta', 'dev'] as const).map((stream) => {
            const data = releases.streams[stream];
            const info = streamInfo[stream];
            const hasRelease = data?.image_url && data?.tag;

            return (
              <div key={stream} style={cardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h2 style={{ margin: '0 0 0.25rem 0' }}>
                      {info.title}
                      <span style={{
                        fontSize: '0.875rem',
                        fontWeight: 'normal',
                        color: stream === 'stable' ? '#198038' : stream === 'beta' ? '#f1c21b' : '#666',
                        marginLeft: '0.5rem',
                      }}>
                        ({info.subtitle})
                      </span>
                    </h2>
                    <p style={{ color: '#666', margin: '0 0 1rem 0' }}>{info.description}</p>
                  </div>
                </div>

                {hasRelease ? (
                  <>
                    <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 1rem 0' }}>
                      Released: {data.release_date}
                      {data.image_download_size && ' • ' + formatSize(data.image_download_size)}
                    </p>
                    <a href={'/latest/' + stream} style={buttonStyle}>Download</a>
                    <a href={data.release_url} style={{ ...buttonStyle, backgroundColor: '#393939' }}>
                      Release Notes
                    </a>
                  </>
                ) : (
                  <>
                    <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 1rem 0' }}>
                      {data?.message || 'No release available yet'}
                    </p>
                    <span style={disabledButtonStyle}>Coming Soon</span>
                  </>
                )}
              </div>
            );
          })}

          <div style={{ ...cardStyle, backgroundColor: '#f4f4f4', marginTop: '2rem' }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Using Raspberry Pi Imager</h3>
            <p style={{ color: '#666', margin: '0 0 1rem 0' }}>
              You can also install RasQberry Two directly using Raspberry Pi Imager with our custom repository.
            </p>
            <a href="/#pi-imager" style={buttonStyle}>View Instructions</a>
          </div>
        </>
      )}

      <p style={{ marginTop: '2rem', fontSize: '0.875rem', color: '#666' }}>
        <a href="/">← Back to home</a>
        {' | '}
        <a href="/RQB-releases.json">View releases JSON</a>
      </p>
    </div>
  );
}
