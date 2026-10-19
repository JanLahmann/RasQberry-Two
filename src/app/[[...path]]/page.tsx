import { promises as fs } from "fs";
import { join, relative } from 'path'
import { PageLayout } from "@/components/PageLayout";
import { extractHeadersFromMd } from '@/utils/extractHeadersFromMd';
import { getPagesFilesPaths } from '@/utils/getPagesFilesPath';
import { getNavItems } from "@/utils/getNavItems";
import { compileMdPage } from "@/utils/compileMdPage";
import { OG_IMAGE, pageMeta } from "@/utils/pageMeta";
import type { Metadata } from "next";

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

// The Markdown file of a route: a direct .md file, or index.md in that directory
async function contentFileOf(path: string[]) {
    const filePath = join(CONTENT_PATH, `${path.join('/')}.md`)
    try {
        await fs.access(filePath)
        return filePath
    } catch {
        return join(CONTENT_PATH, path.join('/'), 'index.md')
    }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
    const path = params.path || []
    const fileContent = await fs.readFile(await contentFileOf(path.length ? path : ['index']), 'utf8')
    const { frontmatter } = await compileMdPage(fileContent)
    const { title, description } = pageMeta(fileContent, frontmatter)
    const url = path.length ? `/${path.join('/')}/` : '/'
    return {
        title: path.length ? title : { absolute: title },
        description,
        alternates: { canonical: url },
        // a page's openGraph/twitter replace the layout's, so repeat the image
        openGraph: { type: 'website', siteName: 'RasQberry Two', title, description, url, images: [OG_IMAGE] },
        twitter: { card: 'summary_large_image', title, description, images: [OG_IMAGE.url] },
    }
}

export default async function Page({ params }: Props) {
    const path = params.path || ['index']
    const filePath = await contentFileOf(path)

    const fileContent = await fs.readFile(filePath, 'utf8');

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
        contentFile={relative(CONTENT_PATH, filePath)}
    >
        {content}
    </PageLayout>
}