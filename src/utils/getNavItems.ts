import { NavItem } from "@/components/HeaderNav"
import { fromKebabToHuman } from "./fromKebabToHuman"

export async function getNavItems(paths: { path: string[] }[]): Promise<NavItem[]> {
    const navItems: NavItem[] = []
    for (const path of paths) {
        addPathsToNavItems(navItems, path)
    }

    return navItems
}

function addPathsToNavItems(navItems: NavItem[], paths: { path: string[] }, level: number = 0) {
    const { path } = paths
    const humanReadableLabel = fromKebabToHuman(path[level])
    if (!humanReadableLabel) {
        return
    }
    const root = navItems.find(item => item.label === humanReadableLabel)
    if (root !== undefined && level < paths.path.length - 1) {
        addPathsToNavItems(root.children, paths, level + 1)

        return
    }
    const url = `/${path.join('/').toLowerCase()}`
    const navItem = { label: humanReadableLabel || 'Home', url, children: [] }
    navItems.push(navItem)

    if (level < paths.path.length - 1) {
        addPathsToNavItems(navItem.children, paths, level + 1)
    }
}