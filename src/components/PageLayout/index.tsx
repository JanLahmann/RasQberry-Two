import { ReactElement, useState } from "react";
import { LeadSpace, Props as LeadSpaceProps } from '@/components/LeadSpace'

import styles from './page-layout.module.scss'
import { Column, Grid } from "@/components/carbon-wrapper";
import { TableOfContent, Props as TableOfContentProps } from "@/components/TableOfContent";
import { HeaderNav, NavItem } from "@/components/HeaderNav";

export interface FrontMatter {
    leadspace?: LeadSpaceProps
}

interface Props {
    children: ReactElement,
    navItems?: NavItem[]
    frontmatter?: FrontMatter
    tableofcontent: TableOfContentProps
}

export function PageLayout({ children, frontmatter: { leadspace } = {}, navItems = [], tableofcontent }: Props) {
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
                    </Column>
                </Grid>
            </Column>
        </Grid>
    </>
}