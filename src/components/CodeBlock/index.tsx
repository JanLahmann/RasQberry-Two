'use client'

import SyntaxHighlighter from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

import styles from './code-block.module.scss'
import { Copy } from '@carbon/icons-react';
import { Tooltip } from '@carbon/react';
import { useRef, useState } from 'react';

interface Props {
    code: string
}

export function CodeBlock({ code }: Props) {
    const [copyText, setCopyText] = useState('Copy')

    function handleOnCopy() {
        setCopyText('Copied!')
    }

    return <div className={styles['code-block']}>
        <SyntaxHighlighter language="bash" style={atomOneDark} PreTag={"code"} CodeTag={"span"} wrapLongLines={true} customStyle={{
            padding: "1rem",
        }}>
            {code}
        </SyntaxHighlighter>
        <div className={styles['code-block__copy-wrapper']}>
            <Tooltip label={copyText}>
                <button type="button" className={styles['code-block__copy-wrapper__btn']} onClick={() => handleOnCopy()}>
                    <Copy />
                </button>
            </Tooltip>
        </div>
    </div>
}
