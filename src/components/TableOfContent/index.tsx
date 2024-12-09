'use client'

import { toKebabCase } from '@/utils/toKebabCase'
import styles from './toc.module.scss'
import { useCallback, useEffect, useState } from 'react'
import clsx from 'clsx'
import { Dropdown } from '@carbon/react'

export interface Props {
    items: { title: string, level: number }[]
}

export function TableOfContent({ items }: Props) {
    const [activeId, setActiveId] = useState<string | null>()
    const [titles, setTitles] = useState<Element[]>([])

    function scrollTo(id: string) {
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
        for (const title of titles) {
            if (isElementInViewport(title)) {
                setActiveId(title.id)
                return
            }
        }
    }, [titles]);

    useEffect(() => {
        if (!titles || titles.length === 0) {
            const titlesFound = document.querySelectorAll('.main-content h1, .main-content h2, .main-content h3, .main-content h4, .main-content h5, .main-content h6')
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
                const id = toKebabCase(`${item.level}-${item.title}`)
                return <li key={id} onClick={() => scrollTo(id)} className={clsx(styles['toc__list__item'], styles[`toc__list__item--${item.level}`], {
                    [styles['toc__list__item--active']]: activeId === id
                })}>{item.title}</li>
            })}
        </ul>
        <Dropdown
            className={styles['toc__dropdown']}
            id="toc-dropdown"
            size="lg"
            onChange={(change: { selectedItem: { title: string; level: number; } }) => navigateToTitle(toKebabCase(change.selectedItem.title))}
            hideLabel={true}
            label="Jump to section"
            items={items.filter(item => item.level === 2)}
        />
    </div>
}