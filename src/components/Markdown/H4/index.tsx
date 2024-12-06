'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h4.module.scss'

interface Props {
    children: ReactNode
}

export function H4({ children }: Props) {
    const id = toKebabCase(`4-${children?.toString() || ''}`)

    return <>
        <h4 id={id} className={styles['h4']}>{children}</h4>
    </>
}