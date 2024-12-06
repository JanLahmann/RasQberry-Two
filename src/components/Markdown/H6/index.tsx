'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h6.module.scss'

interface Props {
    children: ReactNode
}

export function H6({ children }: Props) {
    const id = toKebabCase(`6-${children?.toString() || ''}`)

    return <>
        <h6 id={id} className={styles['h6']}>{children}</h6>
    </>
}