/**
 * Fun with Quantum family manifest (build time only — this site is a static export).
 *
 * Source of truth: family/family.json in JanLahmann/Fun-with-Quantum. Fetched at build time
 * (Fun-with-Quantum fires repository_dispatch `family-updated` at this repo when the roster
 * changes); falls back to the vendored src/data/fwq-family.json, which an automated PR keeps
 * fresh. Never hand-edit the vendored copy.
 */
import vendored from "@/data/fwq-family.json";

export interface FamilyMember { id: string; name: string; url: string; short?: string; footer: boolean }
export interface FamilyManifest {
  version: number; updated: string;
  brand: { id: string; name: string; url: string; footer_lead: string; tagline: { s: string; m: string; l: string } };
  members: FamilyMember[];
}

const MANIFEST_URL = "https://raw.githubusercontent.com/JanLahmann/Fun-with-Quantum/master/family/family.json";
export const SELF_ID = "rasqberry-two";

let cached: Promise<FamilyManifest> | undefined;
export function loadFamily(): Promise<FamilyManifest> {
  if (!cached) cached = load();
  return cached;
}

async function load(): Promise<FamilyManifest> {
  const fallback = vendored as FamilyManifest;
  if (process.env.FWQ_FAMILY_OFFLINE === "1") return fallback;
  try {
    // ?t= busts the ~5-minute raw.githubusercontent CDN cache so a dispatched rebuild sees the new roster.
    // No cache: "no-store" here — that would mark the page dynamic and break `output: "export"`.
    const res = await fetch(process.env.FWQ_FAMILY_URL ?? `${MANIFEST_URL}?t=${Date.now()}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = (await res.json()) as FamilyManifest;
    if (json.version !== 1 || !Array.isArray(json.members)) throw new Error("unexpected manifest shape");
    console.log(`[family] manifest fetched (updated ${json.updated})`);
    return json;
  } catch (err) {
    console.warn(`[family] live manifest unavailable (${(err as Error).message}); using vendored copy (updated ${fallback.updated})`);
    return fallback;
  }
}

/** Every visible member except this site, in manifest order (family home first). */
export function footerLinks(m: FamilyManifest, selfId = SELF_ID): FamilyMember[] {
  return m.members.filter((x) => x.footer && x.id !== selfId);
}
