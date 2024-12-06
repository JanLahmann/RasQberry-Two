import { FrontMatter } from "@/components/PageLayout";
import { compileMDX } from "next-mdx-remote/rsc";
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
import { H1 } from "@/components/Markdown/H1";
import { H2 } from "@/components/Markdown/H2";
import { H3 } from "@/components/Markdown/H3";
import { H4 } from "@/components/Markdown/H4";
import { H5 } from "@/components/Markdown/H5";
import { H6 } from "@/components/Markdown/H6";

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
      h1: ({ children }) => <H1>{children}</H1>,
      h2: ({ children }) => <H2>{children}</H2>,
      h3: ({ children }) => <H3>{children}</H3>,
      h4: ({ children }) => <H4>{children}</H4>,
      h5: ({ children }) => <H5>{children}</H5>,
      h6: ({ children }) => <H6>{children}</H6>,
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
