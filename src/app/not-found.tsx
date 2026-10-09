import Link from 'next/link'
import { join } from 'path'
import { PageLayout } from '@/components/PageLayout'
import { getPagesFilesPaths } from '@/utils/getPagesFilesPath'
import { getNavItems } from '@/utils/getNavItems'

export default async function NotFound() {
    const navItems = await getNavItems(await getPagesFilesPaths(join(process.cwd(), 'content')))

    return <PageLayout navItems={navItems} tableofcontent={{ items: [] }} editLink={false}>
        <div>
            <h1>Page not found</h1>
            <p>This page does not exist (any more). Try one of these:</p>
            <ul>
                <li><Link href="/">Home</Link></li>
                <li><Link href="/03-quantum-computing-demos/01-demo-list/">Demos</Link></li>
                <li><Link href="/#2-getting-started">Getting started</Link></li>
            </ul>
        </div>
    </PageLayout>
}
