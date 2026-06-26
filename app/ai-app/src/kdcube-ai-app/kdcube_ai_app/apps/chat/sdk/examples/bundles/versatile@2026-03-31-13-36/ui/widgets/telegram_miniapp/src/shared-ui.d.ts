declare module '@kdcube/telegram-widget' {
  import type {
    ConversationsPayload,
    TelegramAdminPayload,
    TelegramUser,
    TelegramWidgetCallOperation,
  } from './store/types';

  export type {
    ConversationsPayload,
    TelegramAdminPayload,
    TelegramUser,
    TelegramWidgetCallOperation,
  };

  export function TelegramAdminPanel(props: {
    callOperation: TelegramWidgetCallOperation;
    dataOperation?: string;
    upsertOperation?: string;
    deleteOperation?: string;
    title?: string;
  }): JSX.Element;

  export function TelegramConversationsPanel(props: {
    conversations?: ConversationsPayload;
    reload: () => Promise<void>;
    callOperation: TelegramWidgetCallOperation;
    createOperation?: string;
    switchOperation?: string;
    deleteOperation?: string;
    title?: string;
  }): JSX.Element;

  export function TelegramPendingApproval(props: {
    title?: string;
    message?: string;
    detail?: string;
  }): JSX.Element;
}
