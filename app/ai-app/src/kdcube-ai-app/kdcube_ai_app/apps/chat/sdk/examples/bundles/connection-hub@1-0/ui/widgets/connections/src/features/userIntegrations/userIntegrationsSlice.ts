import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { getOp, postOp } from '../../api/client';
import type {
  UserIntegrationAccount,
  UserIntegrationProvider,
  UserIntegrationsCatalogResult,
  UserIntegrationsMutationResult,
  UserIntegrationsOAuthStartResult,
} from '../../api/types';

export interface UserIntegrationsState {
  enabled: boolean;
  providers: Record<string, UserIntegrationProvider>;
  accounts: UserIntegrationAccount[];
  loading: boolean;
  busy: boolean;
  error: string;
}

const initialState: UserIntegrationsState = {
  enabled: false,
  providers: {},
  accounts: [],
  loading: true,
  busy: false,
  error: '',
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function resultError(result: { error?: string; message?: string } | null | undefined, fallback: string): string {
  return result?.message || result?.error || fallback;
}

export const loadUserIntegrations = createAsyncThunk<UserIntegrationsCatalogResult, void, { rejectValue: string }>(
  'userIntegrations/load',
  async (_arg, { rejectWithValue }) => {
    try {
      const res = await getOp<UserIntegrationsCatalogResult>('user_integrations_catalog');
      if (res?.ok === false) return rejectWithValue(resultError(res, 'Failed to load user integrations'));
      return res || {};
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface ConnectCredentialArgs {
  provider: string;
  appId?: string;
  externalSubject?: string;
  email?: string;
  displayName?: string;
  workspace?: string;
  capabilities: string[];
  secretKind: 'app_password' | 'access_token' | 'api_key' | 'secret';
  secretValue: string;
}

export const connectUserIntegrationCredential = createAsyncThunk<
  UserIntegrationsMutationResult,
  ConnectCredentialArgs,
  { rejectValue: string }
>(
  'userIntegrations/connectCredential',
  async (args, { rejectWithValue }) => {
    try {
      const res = await postOp<UserIntegrationsMutationResult>('user_integrations_connect_credential', {
        provider: args.provider,
        app_id: args.appId || undefined,
        external_subject: args.externalSubject || undefined,
        email: args.email || undefined,
        display_name: args.displayName || undefined,
        workspace: args.workspace || undefined,
        capabilities: args.capabilities,
        [args.secretKind]: args.secretValue,
      });
      if (res?.ok === false) return rejectWithValue(resultError(res, 'Failed to connect integration'));
      return res || {};
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface StartOAuthArgs {
  provider: string;
  appId?: string;
  capabilities: string[];
  returnHint?: string;
}

export const startUserIntegrationOAuth = createAsyncThunk<
  UserIntegrationsOAuthStartResult,
  StartOAuthArgs,
  { rejectValue: string }
>(
  'userIntegrations/startOAuth',
  async (args, { rejectWithValue }) => {
    try {
      const res = await postOp<UserIntegrationsOAuthStartResult>('user_integrations_start_oauth', {
        provider: args.provider,
        app_id: args.appId || undefined,
        capabilities: args.capabilities,
        return_hint: args.returnHint || window.location.href,
      });
      if (res?.ok === false) return rejectWithValue(resultError(res, 'Failed to start OAuth connection'));
      return res || {};
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export const disconnectUserIntegration = createAsyncThunk<
  UserIntegrationsMutationResult,
  { accountId: string },
  { rejectValue: string }
>(
  'userIntegrations/disconnect',
  async ({ accountId }, { rejectWithValue }) => {
    try {
      const res = await postOp<UserIntegrationsMutationResult>('user_integrations_disconnect', {
        account_id: accountId,
      });
      if (res?.ok === false) return rejectWithValue(resultError(res, 'Failed to disconnect integration'));
      return res || {};
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

const userIntegrationsSlice = createSlice({
  name: 'userIntegrations',
  initialState,
  reducers: {
    clearUserIntegrationsError(state) {
      state.error = '';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadUserIntegrations.fulfilled, (state, action: PayloadAction<UserIntegrationsCatalogResult>) => {
        state.loading = false;
        state.enabled = Boolean(action.payload.enabled);
        state.providers = action.payload.providers || {};
        state.accounts = action.payload.accounts || [];
      })
      .addCase(loadUserIntegrations.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? 'Failed to load user integrations';
      });

    builder
      .addCase(connectUserIntegrationCredential.pending, (state) => {
        state.busy = true;
        state.error = '';
      })
      .addCase(connectUserIntegrationCredential.fulfilled, (state, action) => {
        state.busy = false;
        if (action.payload.account) {
          const next = action.payload.account;
          state.accounts = [next, ...state.accounts.filter((account) => account.account_id !== next.account_id)];
        }
      })
      .addCase(connectUserIntegrationCredential.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Failed to connect integration';
      })
      .addCase(startUserIntegrationOAuth.pending, (state) => {
        state.busy = true;
        state.error = '';
      })
      .addCase(startUserIntegrationOAuth.fulfilled, (state) => {
        state.busy = false;
      })
      .addCase(startUserIntegrationOAuth.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Failed to start OAuth connection';
      })
      .addCase(disconnectUserIntegration.pending, (state) => {
        state.busy = true;
        state.error = '';
      })
      .addCase(disconnectUserIntegration.fulfilled, (state, action) => {
        state.busy = false;
        const accountId = action.payload.account_id || action.meta.arg.accountId;
        state.accounts = state.accounts.filter((account) => account.account_id !== accountId);
      })
      .addCase(disconnectUserIntegration.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Failed to disconnect integration';
      });
  },
});

export const { clearUserIntegrationsError } = userIntegrationsSlice.actions;
export default userIntegrationsSlice.reducer;
