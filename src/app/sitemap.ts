import { execFileSync } from "child_process";
import { join } from "path";
import type { MetadataRoute } from "next";
import { getPagesFilesPaths } from "@/utils/getPagesFilesPath";

export const dynamic = "force-static";

const SITE = "https://rasqberry.org";
const CONTENT_PATH = join(process.cwd(), "content");

// The last commit that changed a page's file (needs the full git history,
// see nextjs.yml); none when git can't tell
function lastModified(file: string): string | undefined {
  try {
    return execFileSync("git", ["log", "-1", "--format=%cI", "--", file], { encoding: "utf8" }).trim() || undefined;
  } catch {
    return undefined;
  }
}

// The content pages, as the catch-all route builds them; /latest only redirects
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const paths = await getPagesFilesPaths(CONTENT_PATH);
  const pages = new Map<string, string>();
  for (const { path } of paths) {
    const route = path.map((p) => p.toLowerCase()).filter(Boolean).join("/");
    const url = route ? `${SITE}/${route}/` : `${SITE}/`;
    // "a/b" is a/b.md, "a/" (empty last part) is a/index.md
    const last = path[path.length - 1];
    pages.set(url, last ? join(CONTENT_PATH, ...path) + ".md" : join(CONTENT_PATH, ...path.slice(0, -1), "index.md"));
  }
  return [...pages.keys()].sort().map((url) => ({ url, lastModified: lastModified(pages.get(url)!) }));
}
