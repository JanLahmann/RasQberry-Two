'use client'

interface Props {
    error: Error & { digest?: string }
    reset: () => void
}

export default function Error({ error, reset }: Props) {
    return <p>{error.message}</p>
}