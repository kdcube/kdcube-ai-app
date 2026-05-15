import { configureStore } from '@reduxjs/toolkit';
import memoriesReducer from '../features/memories/memoriesSlice';

export const store = configureStore({
  reducer: {
    memories: memoriesReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
