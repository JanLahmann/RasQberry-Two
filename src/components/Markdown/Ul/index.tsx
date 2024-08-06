import { ReactNode } from "react";
import styles from './ul.module.scss'

interface Props {
    children: ReactNode
}

export function Ul({ children }: Props) {
    return <>
        <ul className={styles['ul']}>{children}</ul>
    </>
}