// Redis Browser Admin App (TypeScript)

import React, {useEffect, useMemo, useState} from 'react';
import ReactDOM from 'react-dom/client';

interface AppSettings {
    baseUrl: string;
    accessToken: string | null;
    idToken: string | null;
    idTokenHeader: string;
    defaultTenant: string;
    defaultProject: string;
    defaultAppBundleId: string;
}

interface RedisKeyItem {
    key: string;
    type: string;
    ttl: number | null;
}

interface RedisKeyDetails {
    key: string;
    type: string;
    ttl: number | null;
    length?: number | null;
    value: unknown;
}

// =============================================================================
// Settings Manager
// =============================================================================

class SettingsManager {
    private readonly PLACEHOLDER_BASE_URL = '{{' + 'CHAT_BASE_URL' + '}}';
    private readonly PLACEHOLDER_ACCESS_TOKEN = '{{' + 'ACCESS_TOKEN' + '}}';
    private readonly PLACEHOLDER_ID_TOKEN = '{{' + 'ID_TOKEN' + '}}';
    private readonly PLACEHOLDER_ID_TOKEN_HEADER = '{{' + 'ID_TOKEN_HEADER' + '}}';
    private readonly PLACEHOLDER_TENANT = '{{' + 'DEFAULT_TENANT' + '}}';
    private readonly PLACEHOLDER_PROJECT = '{{' + 'DEFAULT_PROJECT' + '}}';
    private readonly PLACEHOLDER_BUNDLE_ID = '{{' + 'DEFAULT_APP_BUNDLE_ID' + '}}';

    private settings: AppSettings = {
        baseUrl: '{{CHAT_BASE_URL}}',
        accessToken: '{{ACCESS_TOKEN}}',
        idToken: '{{ID_TOKEN}}',
        idTokenHeader: '{{ID_TOKEN_HEADER}}',
        defaultTenant: '{{DEFAULT_TENANT}}',
        defaultProject: '{{DEFAULT_PROJECT}}',
        defaultAppBundleId: '{{DEFAULT_APP_BUNDLE_ID}}'
    };

    private configReceivedCallback: (() => void) | null = null;

    getBaseUrl(): string {
        if (this.settings.baseUrl === this.PLACEHOLDER_BASE_URL) {
            return window.location.origin;
        }
        try {
            const url = new URL(this.settings.baseUrl);
            if (url.port === 'None' || url.hostname.includes('None')) {
                return window.location.origin;
            }
            const trimmed = this.settings.baseUrl.replace(/\/+$/, '');
            return trimmed.endsWith('/api') ? trimmed.slice(0, -4) : trimmed;
        } catch (e) {
            return window.location.origin;
        }
    }

    getAccessToken(): string | null {
        if (this.settings.accessToken === this.PLACEHOLDER_ACCESS_TOKEN || !this.settings.accessToken) {
            return null;
        }
        return this.settings.accessToken;
    }

    getIdToken(): string | null {
        if (this.settings.idToken === this.PLACEHOLDER_ID_TOKEN || !this.settings.idToken) {
            return null;
        }
        return this.settings.idToken;
    }

    getIdTokenHeader(): string {
        return this.settings.idTokenHeader === this.PLACEHOLDER_ID_TOKEN_HEADER
            ? 'X-ID-Token'
            : this.settings.idTokenHeader;
    }

    getDefaultTenant(): string {
        return this.settings.defaultTenant === this.PLACEHOLDER_TENANT
            ? 'home'
            : this.settings.defaultTenant;
    }

    getDefaultProject(): string {
        return this.settings.defaultProject === this.PLACEHOLDER_PROJECT
            ? 'demo'
            : this.settings.defaultProject;
    }

    hasPlaceholderSettings(): boolean {
        return this.settings.baseUrl === this.PLACEHOLDER_BASE_URL;
    }

    updateSettings(partial: Partial<AppSettings>): void {
        this.settings = { ...this.settings, ...partial };
    }

    onConfigReceived(callback: () => void): void {
        this.configReceivedCallback = callback;
    }

    private applyRuntimeConfig(config: any, options: { notify?: boolean } = {}): boolean {
        const tenant = config.defaultTenant || config.tenant || config.tenant_id;
        const project = config.defaultProject || config.project || config.project_id;
        const idTokenHeader = config.idTokenHeader || config.idTokenHeaderName || config.auth?.idTokenHeaderName;
        const updates: Partial<AppSettings> = {};
        if (config.baseUrl && typeof config.baseUrl === 'string') updates.baseUrl = config.baseUrl;
        if (config.accessToken !== undefined) updates.accessToken = config.accessToken;
        if (config.idToken !== undefined) updates.idToken = config.idToken;
        if (idTokenHeader) updates.idTokenHeader = idTokenHeader;
        if (tenant) updates.defaultTenant = tenant;
        if (project) updates.defaultProject = project;
        if (config.defaultAppBundleId) updates.defaultAppBundleId = config.defaultAppBundleId;
        if (Object.keys(updates).length === 0) return false;
        this.updateSettings(updates);
        if (options.notify !== false) this.configReceivedCallback?.();
        return true;
    }

    private async loadFrontendConfig(): Promise<boolean> {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 1000);
        try {
            const response = await fetch(`${this.getBaseUrl()}/api/cp-frontend-config`, {
                method: 'GET',
                credentials: 'include',
                cache: 'no-store',
                headers: {Accept: 'application/json'},
                signal: controller.signal,
            });
            if (!response.ok) return false;
            const config = await response.json();
            if (!config || typeof config !== 'object') return false;
            return this.applyRuntimeConfig(config, {notify: false});
        } catch {
            return false;
        } finally {
            window.clearTimeout(timeout);
        }
    }

    setupParentListener(): Promise<boolean> {
        const identity = 'REDIS_BROWSER_ADMIN';

        window.addEventListener('message', (event: MessageEvent) => {
            if (event.data.type === 'CONN_RESPONSE' || event.data.type === 'CONFIG_RESPONSE') {
                const requestedIdentity = event.data.identity;
                if (requestedIdentity !== identity) {
                    return;
                }

                if (event.data.config) this.applyRuntimeConfig(event.data.config);
            }
        });

        if (this.hasPlaceholderSettings()) {
            return new Promise<boolean>((resolve) => {
                let resolved = false;
                const finish = (ready: boolean) => {
                    if (resolved) return;
                    resolved = true;
                    resolve(ready);
                };
                const requestParentConfig = () => {
                    window.parent.postMessage({
                        type: 'CONFIG_REQUEST',
                        data: {
                            requestedFields: [
                                'baseUrl', 'accessToken', 'idToken', 'idTokenHeader',
                                'defaultTenant', 'defaultProject', 'defaultAppBundleId'
                            ],
                            identity: identity
                        }
                    }, '*');
                    const timeout = window.setTimeout(() => finish(false), 3000);
                    const originalCallback = this.configReceivedCallback;
                    this.onConfigReceived(() => {
                        window.clearTimeout(timeout);
                        if (originalCallback) originalCallback();
                        finish(true);
                    });
                };
                void this.loadFrontendConfig().then((loaded) => {
                    if (loaded) {
                        finish(true);
                    } else {
                        requestParentConfig();
                    }
                });
            });
        }

        return Promise.resolve(!this.hasPlaceholderSettings());
    }
}

const settings = new SettingsManager();

function appendAuthHeaders(headers: Headers): Headers {
    const accessToken = settings.getAccessToken();
    const idToken = settings.getIdToken();
    const idTokenHeader = settings.getIdTokenHeader();

    if (accessToken) {
        headers.set('Authorization', `Bearer ${accessToken}`);
    }
    if (idToken) {
        headers.set(idTokenHeader, idToken);
    }
    return headers;
}

function makeAuthHeaders(base?: HeadersInit): Headers {
    const headers = new Headers(base);
    return appendAuthHeaders(headers);
}

class RedisBrowserAPI {
    constructor(private basePath: string = '/api/admin/control-plane/redis') {}

    private buildUrl(path: string): string {
        return `${settings.getBaseUrl()}${this.basePath}${path}`;
    }

    async listKeys(prefix: string, cursor: number, limit: number): Promise<{items: RedisKeyItem[]; next_cursor: number}> {
        const params = new URLSearchParams();
        if (prefix) params.set('prefix', prefix);
        params.set('cursor', String(cursor));
        params.set('limit', String(limit));
        const res = await fetch(this.buildUrl(`/keys?${params.toString()}`), {headers: makeAuthHeaders()});
        if (!res.ok) throw new Error('Failed to load keys');
        return await res.json();
    }

    async getKey(key: string, maxItems: number): Promise<RedisKeyDetails> {
        const params = new URLSearchParams();
        params.set('key', key);
        params.set('max_items', String(maxItems));
        const res = await fetch(this.buildUrl(`/key?${params.toString()}`), {headers: makeAuthHeaders()});
        if (!res.ok) throw new Error('Failed to load key');
        return await res.json();
    }

    async deleteKey(key: string): Promise<{status: string; key: string; deleted: number}> {
        const params = new URLSearchParams();
        params.set('key', key);
        const res = await fetch(this.buildUrl(`/key?${params.toString()}`), {
            method: 'DELETE',
            headers: makeAuthHeaders(),
        });
        if (!res.ok) {
            const text = await res.text().catch(() => '');
            throw new Error(text || 'Failed to delete key');
        }
        return await res.json();
    }
}

const api = new RedisBrowserAPI();

const RedisBrowserAdmin: React.FC = () => {
    const [configReady, setConfigReady] = useState(false);
    const [prefix, setPrefix] = useState('');
    const [cursor, setCursor] = useState(0);
    const [keys, setKeys] = useState<RedisKeyItem[]>([]);
    const [selectedKey, setSelectedKey] = useState('');
    const [manualKey, setManualKey] = useState('');
    const [keyDetails, setKeyDetails] = useState<RedisKeyDetails | null>(null);
    const [loading, setLoading] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [limit] = useState(200);

    useEffect(() => {
        settings.setupParentListener().then(() => {
            setConfigReady(true);
        });
    }, []);

    const loadKeys = async (reset: boolean, overridePrefix?: string) => {
        if (!configReady) return;
        setLoading(true);
        setError(null);
        try {
            const activePrefix = overridePrefix !== undefined ? overridePrefix : prefix;
            const nextCursor = reset ? 0 : cursor;
            const data = await api.listKeys(activePrefix, nextCursor, limit);
            setCursor(data.next_cursor || 0);
            setKeys((prev) => reset ? data.items : [...prev, ...data.items]);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const loadKeyDetails = async (key: string) => {
        if (!key) return;
        setLoading(true);
        setError(null);
        setSelectedKey(key);
        try {
            const data = await api.getKey(key, 200);
            setKeyDetails(data);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const deleteCurrentKey = async (key: string) => {
        const resolvedKey = String(key || '').trim();
        if (!resolvedKey) return;
        const confirmed = window.confirm(`Delete Redis key?\n\n${resolvedKey}`);
        if (!confirmed) return;

        setDeleting(true);
        setError(null);
        try {
            await api.deleteKey(resolvedKey);
            setKeyDetails(null);
            setSelectedKey('');
            if (manualKey.trim() === resolvedKey) {
                setManualKey('');
            }
            setKeys((prev) => prev.filter((item) => item.key !== resolvedKey));
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setDeleting(false);
        }
    };

    const summary = useMemo(() => {
        if (!keyDetails) return 'Select a key to inspect.';
        const ttl = keyDetails.ttl === null ? 'n/a' : keyDetails.ttl;
        const len = keyDetails.length ?? 'n/a';
        return `Type: ${keyDetails.type} • TTL: ${ttl} • Size: ${len}`;
    }, [keyDetails]);

    const quickPrefixes = useMemo(() => {
        if (!configReady) return [];
        const tenant = settings.getDefaultTenant();
        const project = settings.getDefaultProject();
        const tp = `${tenant}:${project}:`;
        return [
            { label: 'Queues', value: `${tp}kdcube:chat:prompt:queue` },
            { label: 'Locks', value: `${tp}kdcube:lock` },
            { label: 'Process HB', value: `${tp}kdcube:heartbeat:process` },
            { label: 'Instance HB', value: `${tp}kdcube:heartbeat:instance` },
            { label: 'Capacity', value: `${tp}kdcube:system:capacity` },
            { label: 'Apps', value: 'kdcube:config:bundles:' },
        ];
    }, [configReady]);

    return (
        <div className="min-h-screen bg-[#EEF5F5]">
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <div className="text-[11px] font-bold tracking-[0.14em] uppercase text-[#009C92]">Control Plane</div>
                        <h1 className="text-xl font-bold text-[#0D1E2C] tracking-tight mt-1">Redis Browser</h1>
                        <p className="text-sm text-[#3A5672] mt-1">Explore Redis keys and inspect stored values.</p>
                    </div>
                    <div className={`inline-flex items-center px-2.5 py-1 rounded-full uppercase text-[10px] font-bold border ${(deleting || loading) ? 'text-[#B45309] bg-[rgba(245,158,11,0.1)] border-[rgba(245,158,11,0.4)]' : 'text-[#15803D] bg-[rgba(34,197,94,0.08)] border-[rgba(34,197,94,0.35)]'}`}>{deleting ? 'Deleting…' : loading ? 'Loading…' : 'Ready'}</div>
                </div>

                {error && (
                    <div className="mb-6 rounded-lg border border-[rgba(248,113,113,0.4)] bg-[rgba(248,113,113,0.1)] px-4 py-3 text-[#B91C1C] text-sm">
                        {error}
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
                    <div className="space-y-6">
                        <div className="bg-white border border-[#E6F1F0] rounded-xl p-5 shadow-[0_1px_2px_rgba(13,30,44,0.04)]">
                            <div className="text-[10.5px] font-bold tracking-[0.1em] uppercase text-[#7A99B0] mb-3">Key filter</div>
                            <input
                                className="w-full rounded-md border border-[#D8ECEB] px-3 py-2 text-xs font-mono text-[#0D1E2C] placeholder:text-[#7A99B0] focus:outline-none focus:ring-2 focus:ring-[rgba(1,190,178,0.35)] focus:border-[#01BEB2]"
                                placeholder="Prefix (e.g. kdcube:cp:)"
                                value={prefix}
                                onChange={(e) => setPrefix(e.target.value)}
                            />
                            {quickPrefixes.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-3">
                                    {quickPrefixes.map((item) => (
                                        <button
                                            key={item.label}
                                            className="px-3 py-1 rounded-md text-[11px] font-semibold border border-[#D8ECEB] bg-white text-[#3A5672] hover:bg-[#F6FAFA]"
                                            onClick={() => {
                                                setPrefix(item.value);
                                                setCursor(0);
                                                setKeys([]);
                                                loadKeys(true, item.value);
                                            }}
                                        >
                                            {item.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                            <div className="flex gap-2 mt-3">
                                <button
                                    className="flex-1 px-3 py-2 rounded-md text-xs font-semibold bg-[#4372C3] hover:bg-[#2B4B8A] text-white"
                                    onClick={() => {
                                        setCursor(0);
                                        setKeys([]);
                                        loadKeys(true);
                                    }}
                                >
                                    Search
                                </button>
                                <button
                                    className="flex-1 px-3 py-2 rounded-md text-xs font-semibold border border-[#D8ECEB] bg-white text-[#3A5672] hover:bg-[#F6FAFA] disabled:opacity-50"
                                    onClick={() => loadKeys(false)}
                                    disabled={cursor === 0 && keys.length > 0}
                                >
                                    Load more
                                </button>
                            </div>
                        </div>

                        <div className="bg-white border border-[#E6F1F0] rounded-xl p-5 shadow-[0_1px_2px_rgba(13,30,44,0.04)]">
                            <div className="text-[10.5px] font-bold tracking-[0.1em] uppercase text-[#7A99B0] mb-3">Keys</div>
                            <div className="max-h-72 overflow-auto divide-y divide-[#E6F1F0]">
                                {keys.map((item) => (
                                    <button
                                        key={item.key}
                                        className={`w-full text-left px-3 py-2 text-xs transition ${selectedKey === item.key ? 'bg-[rgba(1,190,178,0.06)]' : 'hover:bg-[#F6FAFA]'}`}
                                        onClick={() => loadKeyDetails(item.key)}
                                    >
                                        <div className="font-mono font-semibold text-[#0D1E2C] truncate">{item.key}</div>
                                        <div className="text-[#7A99B0]">{item.type} • TTL {item.ttl ?? 'n/a'}</div>
                                    </button>
                                ))}
                                {!keys.length && (
                                    <div className="px-3 py-4 text-xs text-[#7A99B0]">No keys loaded.</div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div className="bg-white border border-[#E6F1F0] rounded-xl p-5 shadow-[0_1px_2px_rgba(13,30,44,0.04)]">
                            <div className="text-[10.5px] font-bold tracking-[0.1em] uppercase text-[#7A99B0] mb-3">Inspect key</div>
                            <div className="flex gap-2">
                                <input
                                    className="flex-1 rounded-md border border-[#D8ECEB] px-3 py-2 text-xs font-mono text-[#0D1E2C] placeholder:text-[#7A99B0] focus:outline-none focus:ring-2 focus:ring-[rgba(1,190,178,0.35)] focus:border-[#01BEB2]"
                                    placeholder="Paste key and press Enter"
                                    value={manualKey}
                                    onChange={(e) => setManualKey(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault();
                                            loadKeyDetails(manualKey.trim());
                                        }
                                    }}
                                />
                                <button
                                    className="px-3 py-2 rounded-md text-xs font-semibold bg-[#4372C3] hover:bg-[#2B4B8A] text-white"
                                    onClick={() => loadKeyDetails(manualKey.trim())}
                                >
                                    Load
                                </button>
                            </div>
                        </div>

                        <div className="bg-white border border-[#E6F1F0] rounded-xl p-5 shadow-[0_1px_2px_rgba(13,30,44,0.04)]">
                            <div className="flex items-center justify-between mb-3">
                                <div className="text-[10.5px] font-bold tracking-[0.1em] uppercase text-[#7A99B0]">Key data</div>
                                <div className="flex items-center gap-2">
                                    {selectedKey && (
                                        <button
                                            className="px-3 py-1.5 rounded-md text-[11px] font-semibold border border-[#D8ECEB] bg-white text-[#B91C1C] hover:bg-[rgba(248,113,113,0.08)] disabled:opacity-50"
                                            onClick={() => deleteCurrentKey(selectedKey)}
                                            disabled={deleting || loading}
                                        >
                                            Delete key
                                        </button>
                                    )}
                                    <div className="text-xs font-mono text-[#7A99B0]">{selectedKey || '—'}</div>
                                </div>
                            </div>
                            <div className="text-xs text-[#3A5672] mb-3">{summary}</div>
                            <pre className="font-mono text-xs bg-[#F6FAFA] text-[#0D1E2C] border border-[#E6F1F0] rounded-lg p-4 max-h-[420px] overflow-auto">
                                {keyDetails ? JSON.stringify(keyDetails.value, null, 2) : 'Select a key to load details.'}
                            </pre>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

const rootElement = document.getElementById('root');
if (rootElement) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(<RedisBrowserAdmin />);
}
