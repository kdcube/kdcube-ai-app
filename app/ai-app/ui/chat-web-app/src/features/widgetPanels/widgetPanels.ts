import {createApi, fetchBaseQuery} from "@reduxjs/toolkit/query/react";
import {
    AIBundlesResponse,
    BundleWidgetResponse,
    ConversationsBrowserResponse,
    EconomicsResponse,
    EconomicUsageResponse,
    GatewayResponse,
    RedisBrowserResponse,
    VersatilePreferencesResponse
} from "./types.ts";
import {appendDefaultHeaders} from "../../app/api/utils.ts";
import {ChatScope} from "../chat/chatTypes.ts";

const EconomicsTag = "economics"
const AIBundlesTag = "ai_bundles"
const GatewayTag = "gateway"
const ConversationBrowserTag = "conversation_browser"
const RedisBrowserTag = "redis_browser"
const EconomicUsageTag = "economic_usage"
const VersatilePreferencesTag = "versatile_preferences"
const BundleWidgetTag = "bundle_widget"

export type GetWidgetParams = ChatScope
export interface GetBundleWidgetParams extends ChatScope {
    bundleId: string;
    widgetAlias: string;
}

export const widgetPanelsApiSlice = createApi({
    reducerPath: 'widgetPanels',
    baseQuery: fetchBaseQuery({
        prepareHeaders(headers) {
            return appendDefaultHeaders(headers) as Headers;
        }
    }),
    tagTypes: [EconomicsTag, AIBundlesTag, GatewayTag, ConversationBrowserTag, RedisBrowserTag, EconomicUsageTag, VersatilePreferencesTag, BundleWidgetTag],
    endpoints: builder => ({
        getEconomicsWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/control_plane`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: EconomicsResponse) {
                return res.control_plane[0]
            },
            providesTags: [EconomicsTag],
        }),
        getAIBundlesWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/ai_bundles`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: AIBundlesResponse) {
                return res.ai_bundles[0]
            },
            providesTags: [AIBundlesTag],
        }),
        getGatewayWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/svc_gateway`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: GatewayResponse) {
                return res.svc_gateway[0]
            },
            providesTags: [GatewayTag],
        }),
        getConversationBrowserWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/conversation_browser`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: ConversationsBrowserResponse) {
                return res.conversation_browser[0]
            },
            providesTags: [ConversationBrowserTag],
        }),
        getRedisBrowserWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/redis_browser`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: RedisBrowserResponse) {
                return res.redis_browser[0]
            },
            providesTags: [RedisBrowserTag],
        }),
        getEconomicUsageWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/operations/economic_usage`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: EconomicUsageResponse) {
                return res.economic_usage[0]
            },
            providesTags: [EconomicUsageTag],
        }),
        getVersatilePreferencesWidget: builder.query<string, {
            tenant: string,
            project: string,
        }>({
            query: ({tenant, project}: GetWidgetParams) => {
                const bundleId = "versatile@2026-03-31-13-36";
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/${bundleId}/operations/preferences_widget`,
                    method: 'POST',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                    body: "{}"
                }
            },
            transformResponse(res: VersatilePreferencesResponse) {
                return res.preferences_widget[0]
            },
            providesTags: [VersatilePreferencesTag],
        }),
        getBundleWidget: builder.query<string, GetBundleWidgetParams>({
            query: ({tenant, project, bundleId, widgetAlias}: GetBundleWidgetParams) => {
                return {
                    url: `/api/integrations/bundles/${tenant}/${project}/${bundleId}/widgets/${widgetAlias}`,
                    method: 'GET',
                    headers: [
                        ["Content-Type", "application/json"]
                    ],
                }
            },
            transformResponse(res: BundleWidgetResponse, _meta, arg) {
                const value = res[arg.widgetAlias];
                if (Array.isArray(value)) {
                    return String(value[0] ?? "");
                }
                return String(value ?? "");
            },
            providesTags: [BundleWidgetTag],
        }),
    })
})

export const {
    useGetEconomicsWidgetQuery, useLazyGetEconomicsWidgetQuery,
    useGetAIBundlesWidgetQuery, useLazyGetAIBundlesWidgetQuery,
    useGetGatewayWidgetQuery, useLazyGetGatewayWidgetQuery,
    useGetConversationBrowserWidgetQuery, useLazyGetConversationBrowserWidgetQuery,
    useGetRedisBrowserWidgetQuery, useLazyGetRedisBrowserWidgetQuery,
    useGetEconomicUsageWidgetQuery, useLazyGetEconomicUsageWidgetQuery,
    useGetVersatilePreferencesWidgetQuery, useLazyGetVersatilePreferencesWidgetQuery,
    useGetBundleWidgetQuery, useLazyGetBundleWidgetQuery,
} = widgetPanelsApiSlice
