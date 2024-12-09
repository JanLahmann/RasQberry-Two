import { ReactNode } from "react";
import styles from './img.module.scss'

interface Props {
    src?: string
    alt?: string
    title?: string
}

export function Img({ src, alt, title }: Props) {
    return <>
        <img className={styles['img']} src={src} alt={alt} title={title} />
        {title && <em className={styles['img__caption']}>{title}</em>}
    </>
}