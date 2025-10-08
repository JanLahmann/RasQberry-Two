'use client'

import { ReactNode } from "react";
import styles from './blockquote.module.scss'

interface Props {
    children: ReactNode
}

export function Blockquote({ children }: Props) {
    return <blockquote className={styles['blockquote']}>
        {children}
    </blockquote>
}