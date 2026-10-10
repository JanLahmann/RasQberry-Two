import { join } from "path";
import type { MetadataRoute } from "next";
import { getPagesFilesPaths } from "@/utils/getPagesFilesPath";

export const dynamic = "force-static";

const SITE = "https://rasqberry.org";
const CONTENT_PATH = join(process.cwd(), "content");

// The content pages, as the catch-all route builds them; /latest only redirects
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const paths = await getPagesFilesPaths(CONTENT_PATH);
  const urls = new Set(
    paths.map(({ path }) => {
      const route = path.map((p) => p.toLowerCase()).filter(Boolean).join("/");
      return route ? `${SITE}/${route}/` : `${SITE}/`;
    })
  );
  return [...urls].sort().map((url) => ({ url }));
}
