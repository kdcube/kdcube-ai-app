import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { getOp, postOp } from '../../api/client';
import type { EmailAccount, EmailStatusResult } from '../../api/types';

export interface EmailState {
  accounts: EmailAccount[];
  loading: boolean;
  busy: boolean;
  error: string;
}

const initialState: EmailState = {
  accounts: [],
  loading: true,
  busy: false,
  error: '',
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const loadEmailStatus = createAsyncThunk<EmailAccount[], void, { rejectValue: string }>(
  'email/loadStatus',
  async (_arg, { rejectWithValue }) => {
    try {
      const res = await getOp<EmailStatusResult>('email_accounts_status');
      return Array.isArray(res?.accounts) ? res.accounts : [];
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export interface ConnectIcloudArgs {
  email: string;
  appPassword: string;
  displayName: string;
}

export const connectIcloud = createAsyncThunk<void, ConnectIcloudArgs, { rejectValue: string }>(
  'email/connectIcloud',
  async ({ email, appPassword, displayName }, { rejectWithValue }) => {
    try {
      await postOp('email_connect_app_password', {
        provider: 'icloud',
        email: email.trim(),
        app_password: appPassword,
        display_name: displayName.trim(),
      });
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

export const disconnectEmail = createAsyncThunk<void, string, { rejectValue: string }>(
  'email/disconnect',
  async (accountId, { rejectWithValue }) => {
    try {
      await postOp('email_disconnect_account', { account_id: accountId });
    } catch (e) {
      return rejectWithValue(message(e));
    }
  },
);

const emailSlice = createSlice({
  name: 'email',
  initialState,
  reducers: {
    clearEmailError(state) {
      state.error = '';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadEmailStatus.fulfilled, (state, action: PayloadAction<EmailAccount[]>) => {
        state.loading = false;
        state.accounts = action.payload;
      })
      .addCase(loadEmailStatus.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? 'Failed to load email status';
      });

    [connectIcloud, disconnectEmail].forEach((thunk) => {
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

export const { clearEmailError } = emailSlice.actions;
export default emailSlice.reducer;
