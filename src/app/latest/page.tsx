'use client';

import { useEffect, useState } from 'react';
import { UMAMI, umamiAttrs } from '@/lib/umami';

interface StreamData {
  tag: string | null;
  name: string | null;
  image_url?: string;
  release_url: string;
  release_date?: string;
  image_download_size?: number;
  ab_image_url?: string;
  ab_image_download_size?: number;
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

// A/B default: the A/B image is the recommended download and its button comes
// first, as in the Imager list. Keep in step with AB_DEFAULT in
// .github/scripts/consolidate_json.py on main.
const AB_DEFAULT = true;

// Imager list folders that hold development builds. The first two are the
// names used before the catalogue was regrouped; keep them so this page works
// with either version of RQB-images.json.
const DEV_FOLDERS = ['RasQberry developer builds', 'RasQberry Development Images', 'RasQberry A/B Boot Images'];

function isAbImage(url: string): boolean {
  return url.endsWith('-ab.img.xz');
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
    description: 'The current release, with the newest features',
  },
};

function formatSize(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  return gb.toFixed(1) + ' GB';
}

function extractBranchName(name: string): string {
  // Extract branch name from "RasQberry Two Dev (branch-name-2025-12-19-100018)"
  // and strip the date-timestamp suffix
  const match = name.match(/\(([^)]+)\)/);
  if (match) {
    // Remove the date-timestamp suffix ("-2025-12-19-100018" or " 2025-12-19-100018")
    return match[1].replace(/[ -]\d{4}-\d{2}-\d{2}(-\d{6})?$/, '');
  }
  return name;
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
  // Use only the date portion (first 10 chars) in case release_date contains time
  const dateOnly = releaseDate?.substring(0, 10) || '';
  if (dateOnly && time) {
    return `${dateOnly} ${time}`;
  }
  return dateOnly;
}

export default function LatestPage() {
  const [releases, setReleases] = useState<ReleasesData | null>(null);
  const [devBranches, setDevBranches] = useState<DevBranch[]>([]);
  const [abImages, setAbImages] = useState<ABImage[]>([]);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch releases and images data
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
          const items = imagesData.os_list
            .filter((item) => DEV_FOLDERS.includes(item.name))
            .flatMap((item) => item.subitems || [])
            .filter((item) => item.url);

          // Standard branch builds; the development build itself is the Dev
          // stream above, so it is not repeated here.
          setDevBranches(items
            .filter((item) => !isAbImage(item.url!))
            .map((item) => ({
              name: item.name,
              branch: extractBranchName(item.name),
              url: item.url!,
              release_date: item.release_date,
              image_download_size: item.image_download_size,
            }))
            .filter((item) => item.branch !== 'development'));

          // Beta and stable A/B images are on their own cards above.
          setAbImages(items
            .filter((item) => isAbImage(item.url!))
            .filter((item) => !['beta', 'main'].includes(extractBranchName(item.name)))
            .map((item) => ({
              name: item.name,
              url: item.url!,
              release_date: item.release_date,
              image_download_size: item.image_download_size,
            })));
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

  const outlineButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    backgroundColor: '#fff',
    color: '#0f62fe',
    boxShadow: 'inset 0 0 0 1px #0f62fe',
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
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        The easiest way: let Raspberry Pi Imager 2.0.3+ download and write the image.
        Or download it here and write it with Imager (<strong>Use custom</strong>).
        Writing an image erases the card: copy your notebooks and <code>~/.qiskit</code> off it first.
      </p>
      <p style={{ marginBottom: '1rem' }}>
        <a href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json" style={{ ...buttonStyle, background: 'linear-gradient(45deg, #0f62fe, #9b5cff)', fontWeight: 600 }}
           {...umamiAttrs(UMAMI.imagerOpen, { where: 'latest', stream: releases?.streams.stable?.image_url ? 'stable' : 'beta' })}>
          ▶ Write RasQberry Two to your SD card
        </a>
      </p>
      <p style={{ color: '#666', marginBottom: '2rem' }}>
        Card: 128 GB high-speed (A2/U3) recommended, 16 GB minimum. The recommended image
        holds two systems from 64 GB and one system on smaller cards
        (<a href="/02-software/01-installation-overview/#2-which-image">card sizes</a>).
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
            // As in the Imager list: without a stable release, the beta is the recommended one.
            const recommended = stream === 'stable' || !releases.streams.stable?.image_url;

            return (
              <div key={stream} style={cardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h2 style={{ margin: '0 0 0.25rem 0' }}>
                      {info.title}
                      <span style={{
                        fontSize: '0.875rem',
                        fontWeight: 'normal',
                        color: recommended ? '#198038' : '#b28600',
                        marginLeft: '0.5rem',
                      }}>
                        ({recommended ? 'Recommended' : info.subtitle})
                      </span>
                    </h2>
                    <p style={{ color: '#666', margin: '0 0 1rem 0' }}>{info.description}</p>
                  </div>
                </div>

                {hasRelease ? (
                  <>
                    <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 0.5rem 0' }}>
                      Released: {data.release_date}
                    </p>
                    {data.highlights && data.highlights.length > 0 && (
                      <ul style={{ fontSize: '0.875rem', color: '#444', margin: '0 0 1rem 0', paddingLeft: '1.25rem' }}>
                        {data.highlights.slice(0, 3).map((h, i) => (
                          <li key={i} style={{ marginBottom: '0.25rem' }}>{h}</li>
                        ))}
                      </ul>
                    )}
                    {(() => {
                      const standard = (
                        <a key="std" href={'/latest/' + stream} style={AB_DEFAULT && data.ab_image_url ? outlineButtonStyle : buttonStyle}>
                          Single system{data.image_download_size ? ' (' + formatSize(data.image_download_size) + ')' : ''}
                        </a>
                      );
                      const ab = data.ab_image_url ? (
                        <a key="ab" href={data.ab_image_url} style={buttonStyle}
                           {...umamiAttrs(UMAMI.imageDownload, { file: data.ab_image_url.split('/').pop() ?? '', stream, tag: data.tag ?? '' })}>
                          {AB_DEFAULT ? 'Recommended: A/B image' : 'A/B image'}{data.ab_image_download_size ? ' (' + formatSize(data.ab_image_download_size) + ')' : ''}
                        </a>
                      ) : null;
                      return AB_DEFAULT ? [ab, standard] : [standard, ab];
                    })()}
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

          {/* Development card - shows dev stream + dev-featuresXX branches */}
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
              The newest builds, untested: for developers, not for classrooms or events.
              In Imager they are in <strong>RasQberry developer builds</strong>.
            </p>

            {/* Main development branch (from dev stream) */}
            {releases.streams.dev?.image_url && releases.streams.dev?.tag ? (
              <>
                <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 0.5rem 0' }}>
                  Released: {releases.streams.dev.release_date}
                  {releases.streams.dev.image_download_size && ' • ' + formatSize(releases.streams.dev.image_download_size)}
                </p>
                {releases.streams.dev.highlights && releases.streams.dev.highlights.length > 0 && (
                  <ul style={{ fontSize: '0.875rem', color: '#444', margin: '0 0 1rem 0', paddingLeft: '1.25rem' }}>
                    {releases.streams.dev.highlights.slice(0, 3).map((h, i) => (
                      <li key={i} style={{ marginBottom: '0.25rem' }}>{h}</li>
                    ))}
                  </ul>
                )}
                <a href="/latest/dev" style={buttonStyle}>Download</a>
                <a href={releases.streams.dev.release_url} style={{ ...buttonStyle, backgroundColor: '#393939' }}>
                  Release Notes
                </a>
              </>
            ) : (
              <p style={{ fontSize: '0.875rem', color: '#666', margin: '0 0 1rem 0' }}>
                {releases.streams.dev?.message || 'No development release available'}
              </p>
            )}

            {/* Other dev-featuresXX branches */}
            {devBranches.length > 0 && (
              <details style={{ marginTop: '1.5rem' }}>
                <summary style={{
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  color: '#666',
                  padding: '0.5rem 0',
                }}>
                  Branch builds ({devBranches.length} images, untested)
                </summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
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
              </details>
            )}

            {/* A/B Boot Images collapsible */}
            {abImages.length > 0 && (
              <details style={{ marginTop: '1rem' }}>
                <summary style={{
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  color: '#666',
                  padding: '0.5rem 0',
                }}>
                  A/B images of development and branch builds ({abImages.length})
                </summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
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
              </details>
            )}

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
