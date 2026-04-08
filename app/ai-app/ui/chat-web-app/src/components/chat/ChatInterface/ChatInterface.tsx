/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2025 Elena Viter
 */

// ChatInterface.tsx
import {useMemo} from "react";
import UserInput from "./UserInput.tsx";
import ChatLog from "./ChatLog.tsx";


const ChatInterface = () => {
    return useMemo(() => {
        return <div id={ChatInterface.name}
                    className="flex-1 flex flex-col bg-slate-100 min-h-0 min-w-0 transition-all duration-100 ease-out w-full relative"
        >
            <ChatLog/>
            <UserInput/>
        </div>
    }, [])
};

export default ChatInterface;
