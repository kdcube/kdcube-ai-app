import {
    useLazyGetAIBundlesWidgetQuery,
    useLazyGetConversationBrowserWidgetQuery,
    useLazyGetEconomicsWidgetQuery,
    useLazyGetEconomicUsageWidgetQuery,
    useLazyGetGatewayWidgetQuery,
    useLazyGetRedisBrowserWidgetQuery,
    useLazyGetVersatilePreferencesWidgetQuery
} from "../widgetPanels/widgetPanels.ts";
import {useMemo} from "react";
import {GenericPanel, UrlFramePanel} from "./GenericPanel.tsx";
import {WidgetPanelProps} from "./ChatSidePanel.tsx";
import {useAppSelector} from "../../app/store.ts";
import {selectProject, selectTenant} from "../chat/chatSettingsSlice.ts";

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
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}

export const VersatilePreferencesPanel = ({visible, className}: WidgetPanelProps) => {
    const [trigger, lastArg] = useLazyGetVersatilePreferencesWidgetQuery();

    return useMemo(() => {
        return <GenericPanel trigger={trigger} lastArg={lastArg} visible={visible} className={className}/>
    }, [trigger, lastArg, visible, className]);
}

interface BundleWidgetPanelProps extends WidgetPanelProps {
    bundleId: string | null;
    widgetAlias: string | null;
}

export const BundleWidgetPanel = ({visible, className, bundleId, widgetAlias}: BundleWidgetPanelProps) => {
    const tenant = useAppSelector(selectTenant);
    const project = useAppSelector(selectProject);

    return useMemo(() => {
        const src = bundleId && widgetAlias
            ? `/api/integrations/bundles/${encodeURIComponent(tenant)}/${encodeURIComponent(project)}/${encodeURIComponent(bundleId)}/widgets/${encodeURIComponent(widgetAlias)}`
            : null;
        return <UrlFramePanel visible={visible && !!src} className={className} src={src}/>
    }, [bundleId, className, project, tenant, visible, widgetAlias]);
}
