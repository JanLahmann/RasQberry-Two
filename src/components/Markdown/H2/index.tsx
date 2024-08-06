'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h2.module.scss'

interface Props {
    children: ReactNode
}

export function H2({ children }: Props) {
    const id = toKebabCase(children?.toString() || '')

    return <>
        <h2 id={id} className={styles['h2']}>{children}</h2>
    </>
}