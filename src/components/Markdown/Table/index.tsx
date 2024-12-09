'use client'

import { toKebabCase } from "@/utils/toKebabCase";
import { ReactNode } from "react";
import styles from './table.module.scss'

interface Props {
    children: ReactNode
}

export function Table({ children }: Props) {
    const id = toKebabCase(children?.toString() || '')

    return <div className={styles["table-md"]}>
        <table className={styles["table-md__table"]}>{children}</table>
    </div>
}