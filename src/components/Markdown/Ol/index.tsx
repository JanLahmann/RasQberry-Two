import { ReactNode } from "react";
import styles from './ol.module.scss'

interface Props {
    children: ReactNode
}

export function Ol({ children }: Props) {
    return <>
        <ol className={styles['ol']}>{children}</ol>
    </>
}