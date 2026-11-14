import { NavItem } from "@/components/HeaderNav"
import { fromKebabToHuman } from "./fromKebabToHuman"

// pages linked from the footer only
const NOT_IN_NAV = ["privacy"]

export async function getNavItems(paths: { path: string[] }[]): Promise<NavItem[]> {
    const navItems: NavItem[] = []
    for (const path of paths) {
        if (NOT_IN_NAV.includes(path.path[0])) continue
        addPathsToNavItems(navItems, path)
    }

    // Sort nav items alphabetically (which respects numeric prefixes like 01-, 02-, etc.)
    sortNavItems(navItems)

    return navItems
}

function sortNavItems(navItems: NavItem[]) {
    navItems.sort((a, b) => {
        const urlA = a.url || ''
        const urlB = b.url || ''
        return urlA.localeCompare(urlB)
    })
    // Recursively sort children
    navItems.forEach(item => {
        if (item.children && item.children.length > 0) {
            sortNavItems(item.children)
        }
    })
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