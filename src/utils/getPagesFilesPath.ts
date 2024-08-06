import { promises as fs } from "fs";

export async function getPagesFilesPaths(
  contentPath: string
): Promise<{ path: string[] }[]> {
  const content = await fs.readdir(contentPath, {
    withFileTypes: true,
    recursive: true,
  });

  const paths = content
    .filter((page) => !page.isDirectory())
    .map((page) => {
      const parentPath = page.parentPath.replace(`${contentPath}`, "");
      const slugName = page.name
        .replace("index", "")
        .replace(".md", "")
        .split("/");
      const route = `${parentPath}/${slugName}`.replace(/^\//, "").split("/");

      return {
        path: route,
      };
    });

  return paths;
}
