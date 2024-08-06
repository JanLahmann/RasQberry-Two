'use client'

import SyntaxHighlighter from 'react-syntax-highlighter'
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs'

interface Props {
    code: string
}

export function Code({ code }: Props) {
    return <SyntaxHighlighter language="bash" style={atomOneDark} PreTag={"code"} CodeTag={"span"} wrapLongLines={true} customStyle={{
        display: "inline-block",
        padding: "0.125rem",
        lineHeight: "1.50rem",
        marginBottom: "-0.5rem",
    }}>
        {code}
    </SyntaxHighlighter>
}
