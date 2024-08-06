'use client'

import { toKebabCase } from '@/utils/toKebabCase'
import styles from './toc.module.scss'
import { useCallback, useEffect, useState } from 'react'
import clsx from 'clsx'
import { Dropdown } from '@carbon/react'

export interface Props {
    items: string[]
}

export function TableOfContent({ items }: Props) {
    const [activeId, setActiveId] = useState<string | null>()
    const [titles, setTitles] = useState<Element[]>([])

    function scrollTo(id: string) {
        setActiveId(id)
        document.getElementById(id)?.scrollIntoView({
            behavior: 'smooth'
        });
    }

    function isElementInViewport(el: Element) {
        const rect = el.getBoundingClientRect();

        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }

    const handleScroll = useCallback(() => {
        let found = false
        for (const title of titles) {
            if (isElementInViewport(title)) {
                setActiveId(title.id)
                found = true
                break
            }
        }
    }, [titles]);

    useEffect(() => {
        if (!titles || titles.length === 0) {
            const titlesFound = document.querySelectorAll('.main-content h2')
            setTitles(Array.from(titlesFound))
        }
        window.addEventListener('scroll', handleScroll, { passive: true });

        return () => {
            window.removeEventListener('scroll', handleScroll);
        };
    }, [handleScroll, titles]);

    function navigateToTitle(id: string) {
        document.getElementById(id)?.scrollIntoView({
            behavior: 'smooth'
        });
    }

    return <div className={styles['toc']}>
        <ul className={styles['toc__list']}>
            {items.map(item => {
                const id = toKebabCase(item)
                return <li key={id} onClick={() => scrollTo(id)} className={clsx(styles['toc__list__item'], {
                    [styles['toc__list__item--active']]: activeId === id
                })}>{item}</li>
            })}
        </ul>
        <Dropdown
            className={styles['toc__dropdown']}
            id="toc-dropdown"
            size="lg"
            onChange={(change: { selectedItem: string }) => navigateToTitle(toKebabCase(change.selectedItem))}
            hideLabel={true}
            label="Jump to section"
            items={items}
        />
    </div>
}