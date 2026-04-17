import {useMemo} from "react";
import {LucideProps, X} from "lucide-react";
import {getLucideIconComponent, LucideIcon} from "./utils.ts";

export interface DynamicLucideIconProps extends LucideProps {
    iconName: string | null;
    defaultIcon?: LucideIcon;
}

const DynamicLucideIcon = ({iconName, defaultIcon = X, ...props}: DynamicLucideIconProps) => {
    return useMemo(() => {
        const Icon = getLucideIconComponent(iconName, defaultIcon);
        return <Icon {...props}/>
    }, [defaultIcon, iconName, props])
}

export default DynamicLucideIcon;