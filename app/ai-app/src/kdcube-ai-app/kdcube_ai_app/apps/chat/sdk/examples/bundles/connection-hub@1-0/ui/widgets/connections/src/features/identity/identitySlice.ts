import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { getOp, postOp } from '../../api/client';
import type {
  ConnectionEdge,
  ConnectionEdgeChallengeResult,
  ConnectionEdgesResult,
  ConnectionEdgeMutationResult,
} from '../../api/types';

export interface IdentityState {
  platformUserId: string;
  edges: ConnectionEdge[];
  telegramChallenge: ConnectionEdgeChallengeResult | null;
  loading: boolean;
  busy: boolean;
  error: string;
}

const initialState: IdentityState = {
  platformUserId: '',
  edges: [],
  telegramChallenge: null,
  loading: true,
  busy: false,
  error: '',
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const loadConnectionEdges = createAsyncThunk<ConnectionEdgesResult, void, { rejectValue: string }>(
  'identity/loadEdges',
  async (_arg, { rejectWithValue }) => {
    try {
      return await getOp<ConnectionEdgesResult>('connection_edges_list');
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface LinkIdentityArgs {
  provider: string;
  providerSubject: string;
  label?: string;
}

export const upsertConnectionEdge = createAsyncThunk<ConnectionEdgeMutationResult, LinkIdentityArgs, { rejectValue: string }>(
  'identity/upsertEdge',
  async ({ provider, providerSubject, label }, { rejectWithValue }) => {
    try {
      const res = await postOp<ConnectionEdgeMutationResult>('connection_edge_upsert', {
        provider,
        provider_subject: providerSubject,
        label: label || providerSubject,
      });
      if (res && res.ok === false) {
        return rejectWithValue(res.message || res.error || 'Identity link failed');
      }
      return res;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface RemoveIdentityArgs {
  provider: string;
  providerSubject: string;
}

export const removeConnectionEdge = createAsyncThunk<ConnectionEdgeMutationResult, RemoveIdentityArgs, { rejectValue: string }>(
  'identity/removeEdge',
  async ({ provider, providerSubject }, { rejectWithValue }) => {
    try {
      const res = await postOp<ConnectionEdgeMutationResult>('connection_edge_remove', {
        provider,
        provider_subject: providerSubject,
      });
      if (res && res.ok === false) {
        return rejectWithValue(res.message || res.error || 'Identity unlink failed');
      }
      return res;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export const createTelegramLinkChallenge = createAsyncThunk<ConnectionEdgeChallengeResult, void, { rejectValue: string }>(
  'identity/createTelegramChallenge',
  async (_arg, { rejectWithValue }) => {
    try {
      const res = await postOp<ConnectionEdgeChallengeResult>('connection_edge_challenge_create', { provider: 'telegram' });
      if (res && res.ok === false) {
        return rejectWithValue(res.message || res.error || 'Telegram link challenge failed');
      }
      return res;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export const claimTelegramLinkChallenge = createAsyncThunk<
  ConnectionEdgeChallengeResult,
  { challengeId: string; grants: string[] },
  { rejectValue: string }
>(
  'identity/claimTelegramChallenge',
  async ({ challengeId, grants }, { rejectWithValue }) => {
    try {
      const res = await postOp<ConnectionEdgeChallengeResult>('connection_edge_challenge_claim', {
        challenge_id: challengeId,
        confirmed: true,
        grants,
      });
      if (res && res.ok === false) {
        return rejectWithValue(res.message || res.error || 'Telegram link claim failed');
      }
      return res;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export const loadTelegramLinkChallengeStatus = createAsyncThunk<
  ConnectionEdgeChallengeResult,
  string,
  { rejectValue: string }
>(
  'identity/loadTelegramChallengeStatus',
  async (challengeId, { rejectWithValue }) => {
    try {
      const res = await postOp<ConnectionEdgeChallengeResult>('connection_edge_challenge_status', {
        challenge_id: challengeId,
      });
      if (res && res.ok === false) {
        return rejectWithValue(res.message || res.error || 'Telegram link challenge status failed');
      }
      return res;
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

const identitySlice = createSlice({
  name: 'identity',
  initialState,
  reducers: {
    clearIdentityError(state) {
      state.error = '';
    },
    clearTelegramLinkChallenge(state) {
      state.telegramChallenge = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadConnectionEdges.fulfilled, (state, action: PayloadAction<ConnectionEdgesResult>) => {
        state.loading = false;
        state.platformUserId = action.payload.platform_user_id || '';
        state.edges = Array.isArray(action.payload.edges) ? action.payload.edges : [];
      })
      .addCase(loadConnectionEdges.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? 'Failed to load connection edges';
      });

    [upsertConnectionEdge, removeConnectionEdge].forEach((thunk) => {
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
          state.error = (action.payload as string) ?? 'Identity operation failed';
        });
    });

    builder
      .addCase(createTelegramLinkChallenge.pending, (state) => {
        state.busy = true;
        state.error = '';
      })
      .addCase(createTelegramLinkChallenge.fulfilled, (state, action: PayloadAction<ConnectionEdgeChallengeResult>) => {
        state.busy = false;
        state.telegramChallenge = action.payload;
        if (action.payload.platform_user_id) state.platformUserId = action.payload.platform_user_id;
      })
      .addCase(createTelegramLinkChallenge.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Telegram link challenge failed';
      })
      .addCase(claimTelegramLinkChallenge.pending, (state) => {
        state.busy = true;
        state.error = '';
      })
      .addCase(claimTelegramLinkChallenge.fulfilled, (state, action: PayloadAction<ConnectionEdgeChallengeResult>) => {
        state.busy = false;
        state.telegramChallenge = action.payload;
        if (action.payload.platform_user_id) state.platformUserId = action.payload.platform_user_id;
      })
      .addCase(claimTelegramLinkChallenge.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Telegram link claim failed';
      })
      .addCase(loadTelegramLinkChallengeStatus.fulfilled, (state, action: PayloadAction<ConnectionEdgeChallengeResult>) => {
        state.telegramChallenge = {
          ...(state.telegramChallenge || {}),
          ...action.payload,
        };
        if (action.payload.platform_user_id) state.platformUserId = action.payload.platform_user_id;
      });
  },
});

export const { clearIdentityError, clearTelegramLinkChallenge } = identitySlice.actions;
export default identitySlice.reducer;
