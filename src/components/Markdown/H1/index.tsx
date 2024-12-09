'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h1.module.scss'

interface Props {
    children: ReactNode
}

export function H1({ children }: Props) {
    const id = toKebabCase(`1-${children?.toString() || ''}`)

    return <>
        <h1 id={id} className={styles['h1']}>{children}</h1>
    </>
}