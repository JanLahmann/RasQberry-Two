import Image from "next/image"
import styles from './img.module.scss'

interface Props {
    src?: string
    alt?: string
    title?: string
}

export function Img({ src, alt, title }: Props) {
    if (!src) {
        return <></>
    }

    return <>
        <Image className={styles['img']} src={src} alt={alt || ""} title={title} width={1200} height={800} />
        {title && <em className={styles['img__caption']}>{title}</em>}
    </>
}