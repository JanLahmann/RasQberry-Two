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
                <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.8 }}>
                    RasQberry Two is an independent educational project. IBM®, IBM Quantum®, Qiskit®, and IBM Quantum System Two are trademarks of IBM Corporation. This project is not affiliated with IBM.
                    <br />
                    Licensed under <a href="https://github.com/JanLahmann/RasQberry-Two/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Apache 2.0</a>
                </p>
            </Column>
        </Grid>
    </div>
}