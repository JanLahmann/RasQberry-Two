import { promises as fs } from "fs";
import { join } from 'path'
import { PageLayout } from "@/components/PageLayout";
import { extractHeadersFromMd } from '@/utils/extractHeadersFromMd';
import { getPagesFilesPaths } from '@/utils/getPagesFilesPath';
import { getNavItems } from "@/utils/getNavItems";
import { compileMdPage } from "@/utils/compileMdPage";

interface Props {
    params: {
        path: string[]
    }
}

const CONTENT_PATH = join(process.cwd(), 'content')

export async function generateStaticParams() {
    const paths = await getPagesFilesPaths(CONTENT_PATH)

    return paths.map(path => ({ path: path.path.map(p => p.toLowerCase()) }))
}

export default async function Page({ params }: Props) {
    const path = params.path || ['index']
    const fileContent = await fs.readFile(join(CONTENT_PATH, `${path.join('/')}.md`), 'utf8');

    const paths = await getPagesFilesPaths(CONTENT_PATH)
    const navItems = await getNavItems(paths)

    const { content, frontmatter } = await compileMdPage(fileContent)
    const showToc = !frontmatter.tableOfContent || frontmatter.tableOfContent.disabled !== true
    const tocItems = showToc ? extractHeadersFromMd(fileContent, frontmatter.tableOfContent?.minLevel, frontmatter.tableOfContent?.maxLevel) : []

    return <PageLayout
        frontmatter={{ ...frontmatter }}
        navItems={navItems}
        tableofcontent={{ items: tocItems }}
        pagePath={path}
    >
        {content}
    </PageLayout>
}