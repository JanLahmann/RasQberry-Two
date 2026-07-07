import { Column, Grid } from "../carbon-wrapper"
import styles from "./footer.module.scss"

export function Footer() {
    return <div className={styles["footer"]}>
        <Grid >
            <Column sm={4} md={8} lg={16}>
                <p>RasQberry <strong>Two</strong>: <em>Building a Functional Model of a Quantum Computer at Home</em></p>
                <p style={{ fontSize: '0.875rem', marginTop: '1rem', opacity: 0.8 }}>
                    <a href="/newsletter" style={{ color: 'inherit', textDecoration: 'underline' }}>Subscribe to our newsletter</a> for occasional updates.
                </p>
                <p style={{ fontSize: '0.75rem', marginTop: '1rem', opacity: 0.8, fontFamily: 'monospace', letterSpacing: '0.05em' }}>
                    GOD DOES PLAY DICE. COME PLAY, BUILD, LEARN.
                </p>
                <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.8 }}>
                    Part of the Fun with Quantum family:{' '}
                    <a href="https://fun-with-quantum.org" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Fun with Quantum</a> ·{' '}
                    <a href="https://rasqberry.one" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>RasQberry One</a> ·{' '}
                    <a href="https://quantego.org" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Quantego</a> ·{' '}
                    <a href="https://qutie.org" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Qutie</a> ·{' '}
                    <a href="https://qoffee-maker.org" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Qoffee-Maker</a>
                </p>
                <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.8 }}>
                    Open source, built by Jan-R. Lahmann and the RasQberry community.
                </p>
                <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.8 }}>
                    RasQberry is an independent educational project and is not affiliated with, endorsed by, or sponsored by IBM Corporation. IBM®, IBM Quantum®, Qiskit®, and IBM Quantum System Two are trademarks of International Business Machines Corporation. This project creates an educational tool inspired by IBM&apos;s quantum computing systems for teaching purposes.
                    <br />
                    Licensed under <a href="https://github.com/JanLahmann/RasQberry-Two/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Apache 2.0</a>
                </p>
            </Column>
        </Grid>
    </div>
}