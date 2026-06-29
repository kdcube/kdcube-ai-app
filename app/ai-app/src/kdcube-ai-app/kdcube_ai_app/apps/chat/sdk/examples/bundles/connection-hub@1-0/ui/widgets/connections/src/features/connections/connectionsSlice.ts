import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { getOp, postOp } from '../../api/client';
import type { CatalogEntry, CatalogResult, StartOAuthResult } from '../../api/types';

export interface ConnectionsState {
  catalog: CatalogEntry[];
  loading: boolean;
  busy: boolean;
  error: string;
}

const initialState: ConnectionsState = {
  catalog: [],
  loading: true,
  busy: false,
  error: '',
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const loadCatalog = createAsyncThunk<CatalogEntry[], void, { rejectValue: string }>(
  'connections/loadCatalog',
  async (_arg, { rejectWithValue }) => {
    try {
      const res = await getOp<CatalogResult>('connections_catalog');
      const entries = res?.providers ?? res?.entries ?? [];
      return Array.isArray(entries) ? entries : [];
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface StartOAuthArgs {
  provider: string;
  appId?: string;
  scopes?: string[];
}

// Begins OAuth and returns the authorize URL; the component opens it in a new
// tab (kept out of the thunk so the open() stays close to the user gesture).
export const startOAuth = createAsyncThunk<string | undefined, StartOAuthArgs, { rejectValue: string }>(
  'connections/startOAuth',
  async ({ provider, appId, scopes }, { rejectWithValue }) => {
    try {
      const payload: Record<string, unknown> = { provider };
      if (appId) payload.app_id = appId;
      if (scopes) payload.scopes = scopes;
      const res = await postOp<StartOAuthResult>('connections_start_oauth', payload);
      return res?.authorize_url;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface DisconnectArgs {
  provider: string;
  accountId: string;
}

export const disconnectConnection = createAsyncThunk<void, DisconnectArgs, { rejectValue: string }>(
  'connections/disconnect',
  async ({ provider, accountId }, { rejectWithValue }) => {
    try {
      await postOp('connections_disconnect', { provider, account_id: accountId });
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

const connectionsSlice = createSlice({
  name: 'connections',
  initialState,
  reducers: {
    clearConnectionsError(state) {
      state.error = '';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadCatalog.fulfilled, (state, action: PayloadAction<CatalogEntry[]>) => {
        state.loading = false;
        state.catalog = action.payload;
      })
      .addCase(loadCatalog.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? 'Failed to load catalog';
      });

    // Mutations share busy + error handling.
    [startOAuth, disconnectConnection].forEach((thunk) => {
      builder
        .addCase(thunk.pending, (state) => {
          state.busy = true;
          state.error = '';
        })
        .addCase(thunk.fulfilled, (state) => {
          state.busy = false;
        })
        .addCase(thunk.rejected, (state, action) => {
          state.busy = false;
          state.error = (action.payload as string) ?? 'Operation failed';
        });
    });
  },
});

export const { clearConnectionsError } = connectionsSlice.actions;
export default connectionsSlice.reducer;
