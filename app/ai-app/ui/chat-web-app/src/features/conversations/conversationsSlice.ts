import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {ConversationDescriptor, ConversationsState} from "./conversationsTypes.ts";
import {RootState} from "../../app/store.ts";
import {conversationStatus, newConversation} from "../chat/chatStateSlice.ts";

const conversationsSlice = createSlice({
    name: 'conversations',
    initialState: (): ConversationsState => {
        return {
            conversationDescriptors: null,
            conversationsDescriptorsLoading: false,
            conversationsDescriptorsLoadingError: null,
            conversationLoading: null,
            conversationStatusUpdateRequired: false,
        }
    },
    reducers: {
        setConversationDescriptors: (state, action: PayloadAction<ConversationDescriptor[]>) => {
            state.conversationDescriptors = action.payload
            state.conversationsDescriptorsLoading = false
        },
        setConversationDescriptorsLoading: (state) => {
            state.conversationsDescriptorsLoading = true
        },
        setConversationDescriptorsLoadingError: (state, action: PayloadAction<string>) => {
            state.conversationsDescriptorsLoading = false
            state.conversationsDescriptorsLoadingError = action.payload
        },
        setConversationLoading: (state, action: PayloadAction<string>) => {
            state.conversationLoading = action.payload
        },
        conversationStatusUpdateRequired: (state) => {
            state.conversationStatusUpdateRequired = true
        },
        removeConversation: (state, action: PayloadAction<string>) => {
            if (state.conversationDescriptors) {
                const idx = state.conversationDescriptors.findIndex(c => c.id === action.payload)
                if (idx > -1) {
                    state.conversationDescriptors.splice(idx, 1)
                } else {
                    console.warn(`trying to remove non existing conversation - ${state.conversationDescriptors}`)
                }
            } else {
                console.warn(`trying to remove conversation (${state.conversationDescriptors}) before conversation list is loaded`)
            }
        }
    },
    extraReducers: builder => {
        builder
            .addCase(newConversation, (state) => {
                state.conversationLoading = null
            })
            .addCase(conversationStatus, (state, action) => {
                if (action.payload.conversation.conversation_id !== state.conversationLoading) {
                    return
                }
                state.conversationLoading = null
            })
    }
})

export default conversationsSlice.reducer

export const {
    setConversationDescriptors,
    setConversationDescriptorsLoading,
    setConversationDescriptorsLoadingError,
    setConversationLoading,
    conversationStatusUpdateRequired,
    removeConversation,
} = conversationsSlice.actions
export const selectConversationDescriptors = (state: RootState) => state.conversations.conversationDescriptors
export const selectConversationDescriptorsLoading = (state: RootState) => state.conversations.conversationsDescriptorsLoading
export const selectConversationDescriptorsLoadingError = (state: RootState) => state.conversations.conversationsDescriptorsLoadingError
export const selectIsConversationLoading = (state: RootState) => state.conversations.conversationLoading !== null
export const selectConversationLoading = (state: RootState) => state.conversations.conversationLoading
export const selectConversationStatusUpdateRequired = (state: RootState) => state.conversations.conversationStatusUpdateRequired