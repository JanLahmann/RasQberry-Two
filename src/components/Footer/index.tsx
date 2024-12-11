import { Column, Grid } from "../carbon-wrapper"
import styles from "./footer.module.scss"

export function Footer() {
    return <div className={styles["footer"]}>
        <Grid >
            <Column sm="100%">
                <p>RasQberry <strong>Two</strong>: <em>Building a Functional Model of a Quantum Computer at Home</em></p>
            </Column>
        </Grid>
    </div>
}