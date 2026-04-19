import {useEffect, useMemo} from "react";
import AppRouter from "./AppRouter.tsx";
import './App.css'
import {useAppDispatch, useAppSelector, useAppStore} from "./app/store.ts";
import {
    loadChatSettings,
    selectChatSettingsLoaded,
    selectChatSettingsLoading, selectChatSettingsLoadingError
} from "./features/chat/chatSettingsSlice.ts";
import {initializeEventLogger} from "./services/eventLogger";
import {eventLoggerServiceEnabled} from "./BuildConfig.ts";

const App = () => {
    const dispatch = useAppDispatch();
    const store = useAppStore();
    const settingsLoaded = useAppSelector(selectChatSettingsLoaded)
    const settingsLoading = useAppSelector(selectChatSettingsLoading)
    const settingsLoadingError = useAppSelector(selectChatSettingsLoadingError)

    useEffect(() => {
        // Initialize event logger for error and log tracking
        if (eventLoggerServiceEnabled)
            initializeEventLogger(store);
    }, [store]);

    useEffect(() => {
        if (!settingsLoaded && !settingsLoading && !settingsLoadingError) {
            dispatch(loadChatSettings())
        }
    }, [dispatch, settingsLoaded, settingsLoading, settingsLoadingError]);

    return useMemo(() => {
        if (settingsLoadingError) {
            return <div>An error has occurred</div>
        }

        if (!settingsLoaded) {
            return null;
        }
        return <AppRouter/>
    }, [settingsLoaded, settingsLoadingError])
}

export default App