import {handleContentDownload} from "../../components/shared.ts";
import {getDefaultAuthToken, getDefaultIdToken, getIdTokenHeaderName} from "../../features/auth/helpers.ts";
import {chatAPIBasePath} from "../../BuildConfig.ts";
import {selectStreamIdHeaderName, selectUseAuthCookies} from "../../features/chat/chatSettingsSlice.ts";
import {store} from "../store.ts";
import {selectStreamId} from "../../features/chat/chatStateSlice.ts";

export function appendHeader(name: string, value: string, headers?: HeadersInit) {
    if (!headers) {
        headers = {};
    }
    if (headers instanceof Headers) {
        headers.set(name, value);
    } else if (headers instanceof Array) {
        headers.push([name, value]);
    } else {
        headers[name] = value
    }
    return headers;
}

export function appendCredentials(headers?: HeadersInit, accessToken?: string | null | undefined, idToken?: string | null) {
    if (!headers) {
        headers = {};
    }
    if (accessToken) {
        headers = appendHeader("Authorization", `Bearer ${accessToken}`, headers)
    }
    const headerName = getIdTokenHeaderName();
    if (idToken && headerName) {
        headers = appendHeader(headerName, idToken, headers)
    }
    return headers;
}

export function appendStreamIdHeader(headers?: HeadersInit) {
    headers = headers ?? {}
    const state = store.getState();
    const streamId = selectStreamId(state)
    if (streamId) {
        headers = appendHeader(selectStreamIdHeaderName(state), streamId, headers)
    }
    return headers;
}

export function appendDefaultHeaders(headers?: HeadersInit) {
    headers = headers ?? {}
    if (!selectUseAuthCookies(store.getState())) {
        headers = appendCredentials(headers, getDefaultAuthToken(), getDefaultIdToken());
    }
    headers = appendStreamIdHeader(headers);
    return headers;
}

export const getResourceByRN = async (rn: string) => {
    const headers = appendDefaultHeaders([["Content-Type", "application/json"]]);
    const res = await fetch(
        `${chatAPIBasePath}/api/cb/resources/by-rn`,
        {method: "POST", headers, body: JSON.stringify({rn: rn})}
    );
    if (!res.ok) {
        throw new Error("Failed to get resource by rn");
    }
    return await res.json();
};

export const downloadBlob = async (path: string) => {
    const headers = appendDefaultHeaders({});
    const res = await fetch(
        `${chatAPIBasePath}${path}`,
        {headers}
    );
    if (!res.ok) {
        throw new Error("Failed to get resource by rn");
    }
    return await res.blob()
};

export const downloadResourceByRN = async (rn: string, fileName: string, mimeType?: string | null) => {
    const resource = await getResourceByRN(rn)
    const download_url = resource.metadata.download_url
    const data = await downloadBlob(download_url)
    handleContentDownload(fileName, data, mimeType || "application/octet-stream")
}