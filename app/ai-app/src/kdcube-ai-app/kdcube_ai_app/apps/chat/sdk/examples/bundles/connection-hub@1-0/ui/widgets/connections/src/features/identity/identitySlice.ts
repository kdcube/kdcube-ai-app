import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { getOp, postOp } from '../../api/client';
import type {
  IdentityLink,
  IdentityLinkChallengeResult,
  IdentityLinksResult,
  IdentityMutationResult,
} from '../../api/types';

export interface IdentityState {
  platformUserId: string;
  links: IdentityLink[];
  telegramChallenge: IdentityLinkChallengeResult | null;
  loading: boolean;
  busy: boolean;
  error: string;
}

const initialState: IdentityState = {
  platformUserId: '',
  links: [],
  telegramChallenge: null,
  loading: true,
  busy: false,
  error: '',
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const loadIdentityLinks = createAsyncThunk<IdentityLinksResult, void, { rejectValue: string }>(
  'identity/loadLinks',
  async (_arg, { rejectWithValue }) => {
    try {
      return await getOp<IdentityLinksResult>('identity_links_list');
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

export const linkIdentity = createAsyncThunk<IdentityMutationResult, LinkIdentityArgs, { rejectValue: string }>(
  'identity/link',
  async ({ provider, providerSubject, label }, { rejectWithValue }) => {
    try {
      const res = await postOp<IdentityMutationResult>('identity_link_upsert', {
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

export const removeIdentity = createAsyncThunk<IdentityMutationResult, RemoveIdentityArgs, { rejectValue: string }>(
  'identity/remove',
  async ({ provider, providerSubject }, { rejectWithValue }) => {
    try {
      const res = await postOp<IdentityMutationResult>('identity_link_remove', {
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

export const createTelegramLinkChallenge = createAsyncThunk<IdentityLinkChallengeResult, void, { rejectValue: string }>(
  'identity/createTelegramChallenge',
  async (_arg, { rejectWithValue }) => {
    try {
      const res = await postOp<IdentityLinkChallengeResult>('identity_link_challenge_create', { provider: 'telegram' });
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
  IdentityLinkChallengeResult,
  string,
  { rejectValue: string }
>(
  'identity/claimTelegramChallenge',
  async (challengeId, { rejectWithValue }) => {
    try {
      const res = await postOp<IdentityLinkChallengeResult>('identity_link_challenge_claim', {
        challenge_id: challengeId,
        confirmed: true,
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
  IdentityLinkChallengeResult,
  string,
  { rejectValue: string }
>(
  'identity/loadTelegramChallengeStatus',
  async (challengeId, { rejectWithValue }) => {
    try {
      const res = await postOp<IdentityLinkChallengeResult>('identity_link_challenge_status', {
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
      .addCase(loadIdentityLinks.fulfilled, (state, action: PayloadAction<IdentityLinksResult>) => {
        state.loading = false;
        state.platformUserId = action.payload.platform_user_id || '';
        state.links = Array.isArray(action.payload.links) ? action.payload.links : [];
      })
      .addCase(loadIdentityLinks.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? 'Failed to load identity links';
      });

    [linkIdentity, removeIdentity].forEach((thunk) => {
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
      .addCase(createTelegramLinkChallenge.fulfilled, (state, action: PayloadAction<IdentityLinkChallengeResult>) => {
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
      .addCase(claimTelegramLinkChallenge.fulfilled, (state, action: PayloadAction<IdentityLinkChallengeResult>) => {
        state.busy = false;
        state.telegramChallenge = action.payload;
        if (action.payload.platform_user_id) state.platformUserId = action.payload.platform_user_id;
      })
      .addCase(claimTelegramLinkChallenge.rejected, (state, action) => {
        state.busy = false;
        state.error = action.payload ?? 'Telegram link claim failed';
      })
      .addCase(loadTelegramLinkChallengeStatus.fulfilled, (state, action: PayloadAction<IdentityLinkChallengeResult>) => {
        state.telegramChallenge = {
          ...(state.telegramChallenge || {}),
          ...action.payload,
          telegram_link_url: state.telegramChallenge?.telegram_link_url || action.payload.telegram_link_url,
        };
        if (action.payload.platform_user_id) state.platformUserId = action.payload.platform_user_id;
      });
  },
});

export const { clearIdentityError, clearTelegramLinkChallenge } = identitySlice.actions;
export default identitySlice.reducer;
