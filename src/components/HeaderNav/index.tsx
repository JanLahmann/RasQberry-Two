'use client'

import { Header, HeaderName, HeaderMenuButton, SkipToContent, Grid, Column, HeaderNavigation, HeaderMenuItem, HeaderMenu, SideNav, SideNavItems, HeaderSideNavItems } from "@/components/carbon-wrapper"
import { ReactElement, useState } from "react"

import styles from './header-nav.module.scss'
import Link from "next/link"

export type NavItem = {
    label: string
    url?: string
    children: NavItem[]
}

interface Props {
    items: NavItem[]
}

export function HeaderNav({ items }: Props) {
    const [isSideNavExpanded, setIsSideNavExpanded] = useState(false)
    function onClickSideNavExpand() {
        setIsSideNavExpanded(!isSideNavExpanded)
    }

    return <div className={styles['header-nav']}>
        <Grid>
            <Column sm="100%">
                <Header aria-label="IBM Platform Name">
                    <SkipToContent />
                    <HeaderName href="/" prefix="RasQberry" as={Link}>
                        Two
                    </HeaderName>
                    <HeaderMenuButton aria-label={isSideNavExpanded ? 'Close menu' : 'Open menu'} onClick={onClickSideNavExpand} isActive={isSideNavExpanded} aria-expanded={isSideNavExpanded} />
                    <HeaderNavigation>
                        {items.map(getMenuItem)}
                    </HeaderNavigation>
                    <SideNav aria-label="Side navigation" expanded={isSideNavExpanded} isPersistent={false} onSideNavBlur={onClickSideNavExpand} inert={undefined}>
                        <SideNavItems>
                            <HeaderSideNavItems>
                                {getMenuItem({ label: 'Home', url: '/', children: [] })}
                                {items.map(getMenuItem)}
                            </HeaderSideNavItems>
                        </SideNavItems>
                    </SideNav>
                </Header >
            </Column>
        </Grid>
    </div>
}

function getMenuItem(item: NavItem): ReactElement {
    if (item.children && item.children.length > 0) {
        return <HeaderMenu key={item.label} aria-label={item.label} menuLinkName={item.label}>
            {item.children.map(child => getMenuItem(child))}
        </HeaderMenu>
    }

    return <HeaderMenuItem href={item.url || '/'} key={item.label} as={Link}>{item.label}</HeaderMenuItem>
}