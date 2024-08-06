'use client'

import React from "react";
import Image from 'next/image';

import styles from './lead-space.module.scss'
import clsx from "clsx";
import { Button, Column, Grid } from "@/components/carbon-wrapper";
import { icons } from "@/components/icons";

export interface Props {
    title?: string
    size?: 'short' | 'tall' | 'super'
    copy?: string
    cta?: {
        primary: {
            label: string
            url: string
            icon?: string
        },
        secondary?: {
            label: string
            url: string
            icon?: string
        },
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
                        <Button renderIcon={primaryIcon} iconDescription={cta.primary.label} href={cta.primary.url}>{cta.primary.label}</Button>
                        {cta.secondary && <Button renderIcon={secondaryIcon} iconDescription={cta.secondary.label} href={cta.secondary.url}>{cta.secondary.label}</Button>}
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