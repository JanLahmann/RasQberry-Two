import { ReactElement, useState } from "react";
import { LeadSpace, Props as LeadSpaceProps } from '@/components/LeadSpace'

import styles from './page-layout.module.scss'
import { Column, Grid } from "@/components/carbon-wrapper";
import { TableOfContent, Props as TableOfContentProps } from "@/components/TableOfContent";
import { HeaderNav, NavItem } from "@/components/HeaderNav";
import { Edit } from '@carbon/icons-react';

export interface FrontMatter {
    leadspace?: LeadSpaceProps,
    tableOfContent?: {
        disabled?: boolean
        minLevel?: number
        maxLevel?: number
    }
}

interface Props {
    children: ReactElement,
    navItems?: NavItem[]
    frontmatter?: FrontMatter
    tableofcontent: TableOfContentProps
    pagePath?: string[]
    // The Markdown file behind the page, relative to content/ - a directory
    // route such as 05-contributing/ is served from 05-contributing/index.md.
    contentFile?: string
}

// Generated pages: an edit on GitHub would be overwritten, so no edit link.
const GENERATED_PAGES = ['03-quantum-computing-demos/01-demo-list.md']

export function PageLayout({ children, frontmatter: { leadspace } = {}, navItems = [], tableofcontent, pagePath, contentFile }: Props) {
    // Construct the GitHub edit URL
    const contentPath = contentFile || `${pagePath ? pagePath.join('/') : 'index'}.md`;
    const githubEditUrl = `https://github.com/JanLahmann/RasQberry-Two/edit/gh-pages/content/${contentPath}`;
    const showEditLink = !GENERATED_PAGES.includes(contentPath);

    return <>
        {leadspace && <LeadSpace {...leadspace} />}
        <HeaderNav items={navItems} />
        <Grid className={styles['page-layout__main']}>
            <Column sm="100%">
                <Grid>
                    {tableofcontent && tableofcontent.items.length > 0 && <>
                        <Column sm={4} md={8} lg={4}>
                            <TableOfContent {...tableofcontent} />
                        </Column>
                        <Column sm={4} lg={1} />
                    </>
                    }
                    <Column sm="100%" lg={10} className="main-content">
                        {children}

                        {/* Edit this page footer */}
                        {showEditLink && <div className={styles['page-layout__footer']}>
                            <a
                                href={githubEditUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={styles['page-layout__edit-link']}
                            >
                                <Edit size={16} />
                                <span>Edit this page on GitHub</span>
                            </a>
                        </div>}
                    </Column>
                </Grid>
            </Column>
        </Grid>
    </>
}