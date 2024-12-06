'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h3.module.scss'

interface Props {
    children: ReactNode
}

export function H3({ children }: Props) {
    const id = toKebabCase(`3-${children?.toString() || ''}`)

    return <>
        <h3 id={id} className={styles['h3']}>{children}</h3>
    </>
}