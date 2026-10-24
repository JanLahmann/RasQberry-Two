'use client'

import SyntaxHighlighter from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

// Atom One Dark's comments (#5c6370) are 2.3:1 on its background; #9da5b4 is 5.6:1
const codeStyle = {
    ...atomOneDark,
    'hljs-comment': { ...atomOneDark['hljs-comment'], color: '#9da5b4' },
    'hljs-quote': { ...atomOneDark['hljs-quote'], color: '#9da5b4' },
};

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
        <SyntaxHighlighter language="bash" style={codeStyle} PreTag={"code"} CodeTag={"span"} wrapLongLines={true} customStyle={{
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
