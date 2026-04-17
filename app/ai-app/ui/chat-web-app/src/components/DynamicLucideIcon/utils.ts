import * as lucideIcons from "lucide-react";
import {FC} from "react";
import {LucideProps, X} from "lucide-react";

export type LucideIcon = FC<LucideProps>

export const getLucideIconComponent = (iconName: string | null, defaultIcon: LucideIcon = X) => {
    if (!iconName) {
        return defaultIcon;
    }

    const icon = lucideIcons[iconName as keyof typeof lucideIcons] as LucideIcon;
    if (!icon) {
        console.warn(`Unable to find Lucide icon with name ${iconName}`);
        return defaultIcon
    }

    return icon;
}