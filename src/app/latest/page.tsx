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
  highlights?: string[];
}

interface ReleasesData {
  generated: string;
  streams: {
    [key: string]: StreamData;
  };
}

interface DevBranch {
  name: string;
  branch: string;
  url: string;
  release_date?: string;
  image_download_size?: number;
}

interface ABImage {
  name: string;
  url: string;
  release_date?: string;
  image_download_size?: number;
}

interface ImagesData {
  os_list: Array<{
    name: string;
    subitems?: Array<{
      name: string;
      url?: string;
      release_date?: string;
      image_download_size?: number;
    }>;
  }>;
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
};

function formatSize(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  return gb.toFixed(1) + ' GB';
}

function extractBranchName(name: string): string {
  // Extract branch name from "RasQberry Two Dev (branch-name)"
  const match = name.match(/\(([^)]+)\)/);
  return match ? match[1] : name;
}

function extractTimeFromUrl(url: string): string | null {
  // Extract timestamp from URL like "dev-features05-2025-12-19-075734"
  // Returns formatted time like "07:57" or null if not found
  const match = url.match(/\d{4}-\d{2}-\d{2}-(\d{2})(\d{2})\d{2}/);
  if (match) {
    return `${match[1]}:${match[2]}`;
  }
  return null;
}

function formatDevDate(releaseDate: string | undefined, url: string): string {
  const time = extractTimeFromUrl(url);
  if (releaseDate && time) {
    return `${releaseDate} ${time}`;
  }
  return releaseDate || '';
}

export default function LatestPage() {
  const [releases, setReleases] = useState<ReleasesData | null>(null);
  const [devBranches, setDevBranches] = useState<DevBranch[]>([]);
  const [abImages, setAbImages] = useState<ABImage[]>([]);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch both releases and images data
        const [releasesRes, imagesRes] = await Promise.all([
          fetch('/RQB-releases.json'),
          fetch('/RQB-images.json'),
        ]);

        if (!releasesRes.ok) throw new Error('Failed to fetch releases');
        const releasesData = await releasesRes.json();
        setReleases(releasesData);

        // Extract dev branches from images data
        if (imagesRes.ok) {
          const imagesData: ImagesData = await imagesRes.json();
          const devFolder = imagesData.os_list.find(
            (item) => item.name === 'RasQberry Development Images'
          );
          if (devFolder?.subitems) {
            const branches: DevBranch[] = devFolder.subitems
              .filter((item) => item.url)
              .map((item) => ({
                name: item.name,
                branch: extractBranchName(item.name),
                url: item.url!,
                release_date: item.release_date,
                image_download_size: item.image_download_size,
              }));
            setDevBranches(branches);
          }

          // Extract A/B images
          const abFolder = imagesData.os_list.find(
            (item) => item.name === 'RasQberry A/B Boot Images'
          );
          if (abFolder?.subitems) {
            const images: ABImage[] = abFolder.subitems
              .filter((item) => item.url)
              .map((item) => ({
                name: item.name,
                url: item.url!,
                release_date: item.release_date,
                image_download_size: item.image_download_size,
              }));
            setAbImages(images);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    }
    fetchData();
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
    marginBottom: '0.5rem',
  };

  const smallButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    padding: '0.375rem 0.75rem',
    fontSize: '0.875rem',
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
        Choose a release stream to download the RasQberry Two image, or use a{' '}
        <a href="/#3-simplified-installation-with-custom-pi-imager">customized Raspberry Pi Imager</a> for
        simplified installation.
      </p>

      {error && (
        <p style={{ color: '#c00' }}>Error loading releases: {error}</p>
      )}

      {!releases && !error && <p>Loading releases...</p>}

      {releases && (
        <>
          {/* Stable and Beta cards */}
          {(['stable', 'beta'] as const).map((stream) => {
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
                        color: stream === 'stable' ? '#198038' : '#f1c21b',
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
                    <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 0.5rem 0' }}>
                      Released: {data.release_date}
                      {data.image_download_size && ' • ' + formatSize(data.image_download_size)}
                    </p>
                    {data.highlights && data.highlights.length > 0 && (
                      <ul style={{ fontSize: '0.875rem', color: '#444', margin: '0 0 1rem 0', paddingLeft: '1.25rem' }}>
                        {data.highlights.slice(0, 3).map((h, i) => (
                          <li key={i} style={{ marginBottom: '0.25rem' }}>{h}</li>
                        ))}
                      </ul>
                    )}
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

          {/* Development card with all branches */}
          <div style={cardStyle}>
            <h2 style={{ margin: '0 0 0.25rem 0' }}>
              Development
              <span style={{
                fontSize: '0.875rem',
                fontWeight: 'normal',
                color: '#666',
                marginLeft: '0.5rem',
              }}>
                (Unstable)
              </span>
            </h2>
            <p style={{ color: '#666', margin: '0 0 1rem 0' }}>
              Latest development builds with cutting-edge features. Choose a branch:
            </p>

            {devBranches.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {devBranches.map((branch) => (
                  <div key={branch.branch} style={{
                    padding: '0.75rem',
                    backgroundColor: '#f4f4f4',
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}>
                    <div>
                      <strong style={{ fontSize: '0.9375rem' }}>{branch.branch}</strong>
                      <span style={{ fontSize: '0.8125rem', color: '#666', marginLeft: '0.75rem' }}>
                        {formatDevDate(branch.release_date, branch.url)}
                        {branch.image_download_size && ' • ' + formatSize(branch.image_download_size)}
                      </span>
                    </div>
                    <a href={branch.url} style={smallButtonStyle}>Download</a>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '0.875rem', color: '#666' }}>Loading development branches...</p>
            )}
          </div>

          {/* A/B Boot Images card */}
          {abImages.length > 0 && (
            <div style={cardStyle}>
              <h2 style={{ margin: '0 0 0.25rem 0' }}>
                A/B Boot Images
                <span style={{
                  fontSize: '0.875rem',
                  fontWeight: 'normal',
                  color: '#8a3ffc',
                  marginLeft: '0.5rem',
                }}>
                  (Experimental)
                </span>
              </h2>
              <p style={{ color: '#666', margin: '0 0 1rem 0' }}>
                Images with A/B partition support for safer over-the-air updates.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {abImages.map((image: ABImage, index: number) => (
                  <div key={index} style={{
                    padding: '0.75rem',
                    backgroundColor: '#f4f4f4',
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}>
                    <div>
                      <strong style={{ fontSize: '0.9375rem' }}>{extractBranchName(image.name)}</strong>
                      <span style={{ fontSize: '0.8125rem', color: '#666', marginLeft: '0.75rem' }}>
                        {formatDevDate(image.release_date, image.url)}
                        {image.image_download_size && ' • ' + formatSize(image.image_download_size)}
                      </span>
                    </div>
                    <a href={image.url} style={smallButtonStyle}>Download</a>
                  </div>
                ))}
              </div>
            </div>
          )}

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
