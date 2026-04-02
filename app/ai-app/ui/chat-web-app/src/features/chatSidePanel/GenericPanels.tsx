import {
    useLazyGetAIBundlesWidgetQuery,
    useLazyGetConversationBrowserWidgetQuery,
    useLazyGetEconomicsWidgetQuery,
    useLazyGetEconomicUsageWidgetQuery,
    useLazyGetGatewayWidgetQuery,
    useLazyGetRedisBrowserWidgetQuery, useLazyGetVersatilePreferencesWidgetQuery
} from "../widgetPanels/widgetPanels.ts";
import {useMemo} from "react";
import {GenericPanel} from "./GenericPanel.tsx";
import {WidgetPanelProps} from "./ChatSidePanel.tsx";

export const EconomicsPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetEconomicsWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}
export const AIBundlesPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetAIBundlesWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}
export const GatewayPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetGatewayWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}
export const ConvBrowserPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetConversationBrowserWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}
export const RedisBrowserPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetRedisBrowserWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}
export const EconomicUsagePanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetEconomicUsageWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}
                             reloadOnShow={true}/>
    }, [trigger, lastArg, visible, className]);
}

export const VersatilePreferencesPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetVersatilePreferencesWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}
                             reloadOnShow={true}/>
    }, [trigger, lastArg, visible, className]);
}