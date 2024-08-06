import { ReactNode } from "react";
import styles from './li.module.scss'

interface Props {
    children: ReactNode
}

export function Li({ children }: Props) {
    return <>
        <li className={styles['li']}>{children}</li>
    </>
}