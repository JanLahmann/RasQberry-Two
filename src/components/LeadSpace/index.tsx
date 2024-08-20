'use client'

import React from "react";
import Image from 'next/image';

import styles from './lead-space.module.scss'
import clsx from "clsx";
import { Button, Column, Grid, Link } from "@/components/carbon-wrapper";
import { icons } from "@/components/icons";

interface CTA {
    label: string
    url: string
    icon?: string
    target?: '_blank'
}

export interface Props {
    title?: string
    size?: 'short' | 'tall' | 'super'
    copy?: string
    cta?: {
        primary: CTA,
        secondary?: CTA
    }
    bg?: {
        gradient: boolean,
        image: {
            src: string
            alt: string
        }
    }
}


export function LeadSpace({ title, copy, cta, bg, size = 'tall' }: Props) {
    const primaryIcon = icons[cta?.primary.icon || "arrow-right"]
    const secondaryIcon = icons[cta?.secondary?.icon || "arrow-right"]

    return <div className={clsx(styles['lead-space'], styles[`lead-space--${size}`])}>
        <Grid className={clsx(styles['lead-space__content'], styles[`lead-space__content--${size}`])}>
            <Column sm="100%">
                {title && <h1 className={styles['lead-space__content__title']}>{title}</h1>}
            </Column>
            <Grid className={styles['lead-space__content__bottom']}>
                <Column sm={4} md={6} lg={8}>
                    {copy}
                    {cta && (<div className={styles['lead-space__content__bottom__cta']}>
                        <Link href={cta.primary.url} target={cta.primary.target || '_self'}>
                            <Button renderIcon={primaryIcon}>
                                {cta.primary.label}
                            </Button>
                        </Link>
                        {cta.secondary && <Link renderIcon={secondaryIcon} href={cta.secondary.url} target={cta.primary.target || '_self'}>{cta.secondary.label}</Link>}
                    </div>
                    )}
                </Column>
            </Grid>
        </Grid>
        {bg && <Grid className={styles['lead-space__bg']} condensed>
            <Column sm="100%">
                {bg.gradient !== false && <div className={styles['lead-space__bg__gradient']} />}
                <Image width={1280} height={1280} className={styles['lead-space__bg__image']} src={bg.image.src} alt={bg.image.alt} />
            </Column>
        </Grid>}
    </div>
}