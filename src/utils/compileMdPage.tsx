import { FrontMatter } from "@/components/PageLayout";
import { compileMDX } from "next-mdx-remote/rsc";
import { H2 } from "@/components/Markdown/H2";
import remarkDirective from "remark-directive";
import remarkGfm from "remark-gfm";
import { Ul } from "@/components/Markdown/Ul";
import { Li } from "@/components/Markdown/Li";
import { CodeBlock } from "@/components/CodeBlock";
import { youtubeMd } from '@/utils/remarkPlugins/youtubeMd';
import Children from 'react-children-utilities'
import { Code } from '@/components/Code';
import { Table } from "@/components/Markdown/Table";
import { Ol } from "@/components/Markdown/Ol";

export function compileMdPage(content: string) {
  return compileMDX<FrontMatter>({
    source: content,
    options: {
      parseFrontmatter: true,
      mdxOptions: {
        remarkPlugins: [remarkDirective, remarkGfm, youtubeMd],
      },
    },
    components: {
      h2: ({ children }) => <H2>{children}</H2>,
      pre: ({ children }) => <CodeBlock code={Children.onlyText(children)} />,
      code: ({ children }) => <Code code={Children.onlyText(children)} />,
      ol: ({ children }) => <Ol>{children}</Ol>,
      ul: ({ children }) => <Ul>{children}</Ul>,
      li: ({ children }) => <Li>{children}</Li>,
      customDirective: ({ children }) => <p>{children}</p>,
      table: ({ children }) => <Table>{children}</Table>
    },
  });
}
