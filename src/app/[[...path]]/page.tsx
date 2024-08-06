import { promises as fs } from "fs";
import { join } from 'path'
import { FrontMatter, PageLayout } from "@/components/PageLayout";
import { compileMDX } from 'next-mdx-remote/rsc'
import { H2 } from '@/components/Markdown/H2';
import remarkDirective from 'remark-directive'
import { Ul } from '@/components/Markdown/Ul';
import { Li } from '@/components/Markdown/Li';
import { CodeBlock } from '@/components/CodeBlock';
import Children from 'react-children-utilities'
import { Code } from '@/components/Code';
import { NavItem } from '@/components/HeaderNav';
import { fromKebabToHuman } from '@/utils/fromKebabToHuman';
import { extractH2FromMd } from '@/utils/extractH2FromMd';
import { youtubeMd } from '@/utils/remarkPlugins/youtubeMd';
import { getPagesFilesPaths } from '@/utils/getPagesFilesPath';

interface Props {
    params: {
        path: string[]
    }
}

const contentPath = join(process.cwd(), 'content')

export async function generateStaticParams() {
    const paths = await getPagesFilesPaths(contentPath)

    return paths.map(path => ({ path: path.path.map(p => p.toLowerCase()) }))
}

export default async function Page({ params }: Props) {
    const path = params.path || ['index']
    const file = await fs.readFile(join(contentPath, `${path.join('/')}.md`), 'utf8');
    const navItems = await getNavItems()

    const { content, frontmatter } = await compileMDX<FrontMatter>({
        source: file,
        options: {
            parseFrontmatter: true,
            mdxOptions: {
                remarkPlugins: [remarkDirective, youtubeMd]
            }
        },
        components: {
            h2: ({ children }) => <H2>{children}</H2>,
            pre: ({ children }) => <CodeBlock code={Children.onlyText(children)} />,
            code: ({ children }) => <Code code={Children.onlyText(children)} />,
            ul: ({ children }) => <Ul>{children}</Ul>,
            li: ({ children }) => <Li>{children}</Li>,
            customDirective: ({ children }) => <p>{children}</p>
        },
    })

    const tocItems = extractH2FromMd(file)

    return <PageLayout
        frontmatter={{ ...frontmatter }}
        navItems={navItems}
        tableofcontent={{ items: tocItems }}
    >
        {content}
    </PageLayout>
}

async function getNavItems(): Promise<NavItem[]> {
    const paths = await getPagesFilesPaths(contentPath)
    const navItems: NavItem[] = []
    for (const path of paths) {
        addPathsToNavItems(navItems, path)
    }

    return navItems
}

function addPathsToNavItems(navItems: NavItem[], paths: { path: string[] }, level: number = 0) {
    const { path } = paths
    const humanReadableLabel = fromKebabToHuman(path[level])
    if (!humanReadableLabel) {
        return
    }
    const root = navItems.find(item => item.label === humanReadableLabel)
    if (root !== undefined && level < paths.path.length - 1) {
        addPathsToNavItems(root.children, paths, level + 1)

        return
    }
    const url = `/${path.join('/').toLowerCase()}`
    const navItem = { label: humanReadableLabel || 'Home', url, children: [] }
    navItems.push(navItem)

    if (level < paths.path.length - 1) {
        addPathsToNavItems(navItem.children, paths, level + 1)
    }
}