import {useMemo} from "react";
import {useAppSelector} from "../../app/store.ts";
import {selectAuthConfig, selectProject, selectTenant} from "../chat/chatSettingsSlice.ts";
import {useGetBundlesListQuery} from "./bundlesAPI.ts";
import {selectCurrentBundle} from "./bundlesSlice.ts";
import {selectUserProfile} from "../profile/profile.ts";

const BUILT_IN_WIDGET_ALIASES = new Set([
    "economic_usage",
    "conversation_browser",
    "control_plane",
    "ai_bundles",
    "opex",
    "redis_browser",
    "svc_gateway",
]);

export const useGetBundleWidgets = () => {
    const tenant = useAppSelector(selectTenant)
    const project = useAppSelector(selectProject)

    const {data} = useGetBundlesListQuery({tenant, project})

    const userProfile = useAppSelector(selectUserProfile)
    const authConfig = useAppSelector(selectAuthConfig)

    const authDisabled = useMemo(() => authConfig.authType === "none", [authConfig.authType])

    const currentBundleId = useAppSelector(selectCurrentBundle)
    const currentBundleData = useMemo(() => {
        if (!data || !currentBundleId) return null;
        return data.bundles[currentBundleId] || null;
    }, [currentBundleId, data]);


    return useMemo(() => {
        const allWidgets = currentBundleData?.widgets || [];
        const userRoles = userProfile?.roles ?? []
        const widgets = allWidgets.filter((widget) => {
            return !BUILT_IN_WIDGET_ALIASES.has(widget.alias) && (!widget.roles || widget.roles.length === 0 || authDisabled || (!!userProfile && widget.roles.every(r=>userRoles.includes(r))))
        });

        // An app converses only when it declares a reactive entrypoint
        // (@on_reactive_event -> manifest.on_message). While the registry is
        // still loading we assume conversational to avoid a scene flash.
        const conversational = currentBundleData ? Boolean(currentBundleData.on_message) : true;

        return {
            currentBundleId,
            currentBundleData,
            widgets,
            allWidgets,
            conversational
        }
    }, [authDisabled, currentBundleData, currentBundleId, userProfile])
}