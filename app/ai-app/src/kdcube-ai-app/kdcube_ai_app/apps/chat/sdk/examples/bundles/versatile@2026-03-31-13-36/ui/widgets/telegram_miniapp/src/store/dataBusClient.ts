import { io, type Socket } from 'socket.io-client';
import { callOperation } from './apiClient';
import { settings } from './settings';
import { isTelegramWebApp } from '../telegram/utils';

const ECHO_SUBJECT = 'versatile.echo';

interface FederatedClaimPayload {
  ok?: boolean;
  federated_token?: string;
  session_id?: string;
  expires_at?: number;
  bundle_id?: string;
  allowed_subjects?: string[];
}

interface ProfilePayload {
  session_id?: string;
}

interface SocketContext {
  auth: Record<string, unknown>;
  sessionId: string;
  key: string;
}

export interface DataBusEchoOutcome {
  ack: Record<string, unknown>;
  event?: Record<string, unknown>;
  messageId: string;
}

export interface DataBusServiceEnvelope {
  type?: string;
  data?: Record<string, unknown>;
  event?: Record<string, unknown>;
  service?: Record<string, unknown>;
  conversation?: Record<string, unknown>;
}

let dataBusSocket: Socket | null = null;
let dataBusSocketKey = '';
let dataBusSessionId = '';
let dataBusConnectPromise: Promise<void> | null = null;

function createLocalId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function authHeaders(base?: HeadersInit): Headers {
  const headers = new Headers(base);
  const accessToken = settings.getAccessToken();
  const idToken = settings.getIdToken();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (idToken) headers.set(settings.getIdTokenHeader(), idToken);
  return headers;
}

async function fetchProfileSessionId(): Promise<string> {
  const response = await fetch(`${settings.getBaseUrl()}/profile`, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
    headers: authHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) throw new Error(`Profile request failed: ${response.status}`);
  const profile = (await response.json()) as ProfilePayload;
  const sessionId = String(profile.session_id || '').trim();
  if (!sessionId) throw new Error('Profile did not return a session_id.');
  return sessionId;
}

async function buildSocketContext(): Promise<SocketContext> {
  const baseAuth: Record<string, unknown> = {
    tenant: settings.getTenant(),
    project: settings.getProject(),
    bundle_id: settings.getBundleId(),
  };
  const key = [
    settings.getBaseUrl(),
    settings.getTenant(),
    settings.getProject(),
    settings.getBundleId(),
    isTelegramWebApp() ? 'telegram' : 'browser',
  ].join('|');

  if (isTelegramWebApp()) {
    const claim = await callOperation<FederatedClaimPayload>('federated_data_bus_claim', {});
    const token = String(claim.federated_token || '').trim();
    if (!token) throw new Error('Federated Data Bus token was not issued.');
    const sessionId = String(claim.session_id || '').trim();
    if (!sessionId) throw new Error('Federated Data Bus claim did not return a session_id.');
    return {
      key,
      sessionId,
      auth: {
        ...baseAuth,
        federated_token: token,
      },
    };
  }

  const sessionId = await fetchProfileSessionId();
  const accessToken = settings.getAccessToken();
  const idToken = settings.getIdToken();
  return {
    key,
    sessionId,
    auth: {
      ...baseAuth,
      user_session_id: sessionId,
      ...(accessToken ? { bearer_token: accessToken } : {}),
      ...(idToken ? { id_token: idToken } : {}),
    },
  };
}

function resetDataBusSocket(socket: Socket): void {
  if (dataBusSocket === socket) {
    dataBusSocket = null;
    dataBusSocketKey = '';
    dataBusSessionId = '';
    dataBusConnectPromise = null;
  }
}

function createSocket(auth: Record<string, unknown>): Socket {
  const socket = io(settings.getBaseUrl(), {
    path: '/socket.io',
    transports: ['websocket'],
    upgrade: false,
    withCredentials: true,
    autoConnect: false,
    auth,
    reconnectionAttempts: 0,
  });
  socket.on('connect_error', (error: Error) => {
    console.warn('[telegram-miniapp:data-bus] connect_error', { message: error.message });
  });
  socket.on('disconnect', (reason: string) => {
    console.info('[telegram-miniapp:data-bus] disconnected', { reason });
  });
  return socket;
}

function ensureSocketConnected(socket: Socket): Promise<void> {
  if (socket.connected) return Promise.resolve();
  if (dataBusConnectPromise) return dataBusConnectPromise;
  dataBusConnectPromise = new Promise<void>((resolve, reject) => {
    let timeout: number | undefined;
    const cleanup = () => {
      if (timeout !== undefined) window.clearTimeout(timeout);
      socket.off('connect', onConnect);
      socket.off('connect_error', onConnectError);
    };
    function onConnect() {
      cleanup();
      resolve();
    }
    function onConnectError(error: unknown) {
      cleanup();
      socket.disconnect();
      resetDataBusSocket(socket);
      reject(error instanceof Error ? error : new Error(String(error)));
    }

    timeout = window.setTimeout(() => {
      cleanup();
      socket.disconnect();
      resetDataBusSocket(socket);
      reject(new Error('Timed out connecting to Socket.IO.'));
    }, 8000);
    socket.once('connect', onConnect);
    socket.once('connect_error', onConnectError);
    socket.connect();
  }).finally(() => {
    dataBusConnectPromise = null;
  });
  return dataBusConnectPromise;
}

async function dataBusSocketFor(): Promise<{ socket: Socket; sessionId: string }> {
  const context = await buildSocketContext();
  if (dataBusSocket && dataBusSocketKey === context.key) {
    dataBusSocket.auth = context.auth;
    dataBusSessionId = context.sessionId;
    await ensureSocketConnected(dataBusSocket);
    return { socket: dataBusSocket, sessionId: context.sessionId };
  }
  if (dataBusSocket) {
    dataBusSocket.disconnect();
    resetDataBusSocket(dataBusSocket);
  }
  const socket = createSocket(context.auth);
  dataBusSocket = socket;
  dataBusSocketKey = context.key;
  dataBusSessionId = context.sessionId;
  await ensureSocketConnected(socket);
  return { socket, sessionId: context.sessionId };
}

function waitForEchoEvent(socket: Socket, messageId: string): Promise<Record<string, unknown> | undefined> {
  return new Promise((resolve) => {
    const timeout = window.setTimeout(() => {
      socket.off('chat_service', onServiceEvent);
      resolve(undefined);
    }, 8000);

    function onServiceEvent(payload: unknown) {
      if (!payload || typeof payload !== 'object') return;
      const envelope = payload as Record<string, unknown>;
      if (envelope.type !== 'kdcube.data_bus.result') return;
      const data = envelope.data;
      if (!data || typeof data !== 'object') return;
      if ((data as Record<string, unknown>).message_id !== messageId) return;
      window.clearTimeout(timeout);
      socket.off('chat_service', onServiceEvent);
      resolve(envelope);
    }

    socket.on('chat_service', onServiceEvent);
  });
}

export async function getDataBusSessionId(): Promise<string> {
  const { sessionId } = await dataBusSocketFor();
  return sessionId;
}

export function subscribeDataBusServiceEvents(
  onEvent: (envelope: DataBusServiceEnvelope) => void,
  onError?: (error: Error) => void,
): () => void {
  let closed = false;
  let subscribedSocket: Socket | null = null;
  const onService = (payload: unknown) => {
    if (!payload || typeof payload !== 'object') return;
    onEvent(payload as DataBusServiceEnvelope);
  };

  void (async () => {
    try {
      const { socket } = await dataBusSocketFor();
      if (closed) return;
      subscribedSocket = socket;
      socket.on('chat_service', onService);
    } catch (error) {
      if (closed) return;
      onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  })();

  return () => {
    closed = true;
    if (subscribedSocket) {
      subscribedSocket.off('chat_service', onService);
    }
  };
}

export async function sendDataBusEcho(payload: Record<string, unknown>): Promise<DataBusEchoOutcome> {
  const { socket } = await dataBusSocketFor();
  const messageId = createLocalId('dbmsg');
  const result = waitForEchoEvent(socket, messageId);

  const ack = await socket.timeout(8000).emitWithAck('data_bus.publish', {
    schema: 'kdcube.data_bus.ingress.v1',
    bundle_id: settings.getBundleId(),
    messages: [
      {
        message_id: messageId,
        subject: ECHO_SUBJECT,
        object_ref: 'probe:memory',
        idempotency_key: createLocalId('echo'),
        payload,
        client: {
          widget: 'telegram_miniapp',
          source: 'memory_page',
        },
      },
    ],
  });
  const ackObject = ack as Record<string, unknown>;
  const status = String(ackObject.status || '');
  if (status !== 'accepted' && status !== 'partial') {
    const rejected = Array.isArray(ackObject.rejected) ? ackObject.rejected : [];
    const first = rejected[0] as Record<string, unknown> | undefined;
    throw new Error(String(first?.error || `Data Bus publish rejected: ${status || 'unknown'}`));
  }
  const event = await result;
  return { ack: ackObject, event, messageId };
}
