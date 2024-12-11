import Image from "next/image"
import styles from './img.module.scss'

interface Props {
    src?: string
    alt?: string
    title?: string
}

const IMAGE_PLACEHOLDER = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAAaADAAQAAAABAAAAAQAAAAD5Ip3+AAAADUlEQVQIHWN4//79fwAJawPNDeosawAAAABJRU5ErkJggg=='

export function Img({ src, alt, title }: Props) {
    if (!src) {
        return <></>
    }

    return <a href={src} target="_blank">
        <Image
            className={styles['img']}
            src={src}
            alt={alt || ""}
            title={title}
            width={800}
            height={600}
            placeholder={IMAGE_PLACEHOLDER}
        />
        {title && <em className={styles['img__caption']}>{title}</em>}
    </a>
}