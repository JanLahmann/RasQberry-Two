'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './h5.module.scss'

interface Props {
    children: ReactNode
}

export function H5({ children }: Props) {
    const id = toKebabCase(`5-${children?.toString() || ''}`)

    return <>
        <h5 id={id} className={styles['h5']}>{children}</h5>
    </>
}