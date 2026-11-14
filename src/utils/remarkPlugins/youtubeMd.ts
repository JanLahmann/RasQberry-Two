import { visit } from "unist-util-visit";

export function youtubeMd() {
  return (tree: any, file: any) => {
    visit(tree, function (node) {
      if (
        node.type === "containerDirective" ||
        node.type === "leafDirective" ||
        node.type === "textDirective"
      ) {
        if (node.name !== "youtube") return;

        const data = node.data || (node.data = {});
        const attributes = node.attributes || {};
        const id = attributes.id;

        if (node.type === "textDirective") {
          file.fail(
            "Unexpected `:youtube` text directive, use two colons for a leaf directive",
            node
          );
        }

        if (!id) {
          file.fail("Unexpected missing `id` on `youtube` directive", node);
        }

        // click to load (privacy page): nothing comes from YouTube until the
        // visitor plays the video; YOUTUBE_CLICK in layout.tsx swaps in the
        // youtube-nocookie player
        data.hName = "a";
        data.hProperties = {
          href: "https://www.youtube.com/watch?v=" + id,
          class: "youtube-click",
          "data-youtube-id": id,
        };
        data.hChildren = [{ type: "text", value: "▶ Play the video (loads it from YouTube)" }];
      }
    });
  };
}
