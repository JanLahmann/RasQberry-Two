'use client'

import React, { useEffect, useState } from "react";
import Image from 'next/image';

import styles from './lead-space.module.scss'
import clsx from "clsx";
import { Button, Column, Grid, Link } from "@/components/carbon-wrapper";
import { icons } from "@/components/icons";
import { umamiAttrs } from "@/lib/umami";

interface CTA {
    label: string
    url: string
    icon?: string
    target?: '_blank'
    // "gradient": the site-wide call-to-action button (a.cta-button), e.g. "Write RasQberry Two to your SD card"
    style?: 'gradient'
    // Umami click event: { event: "RasQberry Two: ...", <key>: <value>, ... } (src/lib/umami.ts)
    umami?: { event: string } & Record<string, string>
}

function ctaEvent(cta: CTA): Record<string, string> {
    if (!cta.umami) return {};
    const { event, ...data } = cta.umami;
    return umamiAttrs(event, data);
}

interface CTAs {
    primary: CTA,
    secondary?: CTA,
    tertiary?: CTA
}

export interface Props {
    title?: string
    variant: 'light' | 'dark'
    size?: 'short' | 'tall' | 'super'
    copy?: string
    cta?: CTAs
    // A line under the buttons that opens Ket, the helper; shown only while the
    // widget is on the page (src/lib/ket.mjs decides where it loads)
    ket?: string
    // On a Pi (rasqberry.org/?from=pi): this copy and these links instead
    pi?: {
        copy?: string
        cta?: CTAs
        ket?: string
    }
    bg?: {
        gradient: boolean,
        image: {
            src: string
            alt: string
        }
    }
}


function CallToAction({ cta }: { cta: CTAs }) {
    const primaryIcon = icons[cta.primary.icon || "arrow-right"]
    const secondaryIcon = icons[cta.secondary?.icon || "arrow-right"]
    const tertiaryIcon = icons[cta.tertiary?.icon || "arrow-right"]
    return <div className={styles['lead-space__content__bottom__cta']}>
        {cta.primary.style === 'gradient'
            ? <a className="cta-button" href={cta.primary.url} target={cta.primary.target || '_self'} {...ctaEvent(cta.primary)}>▶ {cta.primary.label}</a>
            : <Link href={cta.primary.url} target={cta.primary.target || '_self'}>
                <Button renderIcon={primaryIcon}>
                    {cta.primary.label}
                </Button>
            </Link>}
        {cta.secondary && <Link renderIcon={secondaryIcon} href={cta.secondary.url} target={cta.secondary.target || '_self'} {...ctaEvent(cta.secondary)}>{cta.secondary.label}</Link>}
        {cta.tertiary && <Link renderIcon={tertiaryIcon} href={cta.tertiary.url} target={cta.tertiary.target || '_self'} {...ctaEvent(cta.tertiary)}>{cta.tertiary.label}</Link>}
    </div>
}

// The widget (div#fwq-assistant, open shadow root) has no open() call: press
// its own floating button, unless the panel is open already
function openKet() {
    const button = document.getElementById('fwq-assistant')?.shadowRoot?.querySelector<HTMLButtonElement>('.fa-open');
    if (button && button.getAttribute('aria-expanded') !== 'true') button.click();
}

function KetPrompt({ label }: { label: string }) {
    const [ready, setReady] = useState(false);
    useEffect(() => {
        // The host only: its shadow content may be filled after it is added
        const found = () => !!document.getElementById('fwq-assistant');
        if (found()) { setReady(true); return; }
        const observer = new MutationObserver(() => { if (found()) { setReady(true); observer.disconnect(); } });
        observer.observe(document.body, { childList: true });
        return () => observer.disconnect();
    }, []);
    if (!ready) return null;
    return <p className={styles['lead-space__ket']}>
        {/* No Umami attribute: the widget counts its own "assistant open" */}
        <button type="button" onClick={openKet}><span aria-hidden="true">💬</span> {label}</button>
    </p>
}

export function LeadSpace({ title, copy, cta, ket, pi, bg, size = 'tall', variant = 'light' }: Props) {
    return <div className={clsx(styles['lead-space'], styles[`lead-space--${size}`])}>
        <Grid className={clsx(styles['lead-space__content'], styles[`lead-space__content--${size}`], styles[`lead-space__content--${variant}`])}>
            <Column sm="100%">
                {title && <h1 className={clsx(styles['lead-space__content__title'], styles[`lead-space__content__title--${variant}`])} dangerouslySetInnerHTML={{ __html: title }}></h1>}
            </Column>
            <Grid className={styles['lead-space__content__bottom']}>
                <Column sm={4} md={6} lg={8}>
                    <div className={pi ? 'not-pi' : undefined}>
                        {copy && <div dangerouslySetInnerHTML={{ __html: copy }}></div>}
                        {cta && <CallToAction cta={cta} />}
                        {ket && <KetPrompt label={ket} />}
                    </div>
                    {pi && <div className="only-pi">
                        {pi.copy && <div dangerouslySetInnerHTML={{ __html: pi.copy }}></div>}
                        {pi.cta && <CallToAction cta={pi.cta} />}
                        {pi.ket && <KetPrompt label={pi.ket} />}
                    </div>}
                </Column>
            </Grid>
        </Grid>
        {bg && <Grid className={styles['lead-space__bg']} condensed>
            <Column sm="100%">
                {bg.gradient !== false && <div className={clsx(styles['lead-space__bg__gradient'], styles[`lead-space__bg__gradient--${variant}`])} />}
                <Image width={1280} height={1280} className={styles['lead-space__bg__image']} src={bg.image.src} alt={bg.image.alt} />
            </Column>
        </Grid>}
    </div>
}