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

        data.hName = "iframe";
        data.hProperties = {
          src: "https://www.youtube.com/embed/" + id,
          frameBorder: 0,
          allow: "picture-in-picture",
          allowFullScreen: true,
          class: 'youtube-iframe'
        };
      }
    });
  };
}
