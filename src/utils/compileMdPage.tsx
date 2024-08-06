import { FrontMatter } from "@/components/PageLayout";
import { compileMDX } from "next-mdx-remote/rsc";
import { H2 } from "@/components/Markdown/H2";
import remarkDirective from "remark-directive";
import { Ul } from "@/components/Markdown/Ul";
import { Li } from "@/components/Markdown/Li";
import { CodeBlock } from "@/components/CodeBlock";
import { youtubeMd } from '@/utils/remarkPlugins/youtubeMd';
import Children from 'react-children-utilities'
import { Code } from '@/components/Code';

export function compileMdPage(content: string) {
  return compileMDX<FrontMatter>({
    source: content,
    options: {
      parseFrontmatter: true,
      mdxOptions: {
        remarkPlugins: [remarkDirective, youtubeMd],
      },
    },
    components: {
      h2: ({ children }) => <H2>{children}</H2>,
      pre: ({ children }) => <CodeBlock code={Children.onlyText(children)} />,
      code: ({ children }) => <Code code={Children.onlyText(children)} />,
      ul: ({ children }) => <Ul>{children}</Ul>,
      li: ({ children }) => <Li>{children}</Li>,
      customDirective: ({ children }) => <p>{children}</p>,
    },
  });
}
