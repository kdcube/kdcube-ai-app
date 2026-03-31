/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2025 Elena Viter
 */

// Chat.tsx
import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";

import ChatInterface from "./ChatInterface/ChatInterface.tsx";
import {useAppDispatch, useAppSelector} from "../../app/store.ts";
import {selectChatStayConnected, selectConversationId, selectCurrentTurn,} from "../../features/chat/chatStateSlice.ts";
import ChatSidePanel from "../../features/chatSidePanel/ChatSidePanel.tsx";
import ChatHeader from "./ChatHeader.tsx";
import AnimatedExpander from "../AnimatedExpander.tsx";
import ChatCanvas from "../../features/canvas/ChatCanvas.tsx";
import {CanvasItemLink, ChatCanvasContext, ChatCanvasContextValue} from "../../features/canvas/canvasContext.tsx";
import {getCanvasArtifactTypes, getCanvasItemLinkGenerator} from "../../features/extensions/canvasExtensions.ts";
import useSharedConfigProvider from "../../features/sharedConfigProvider/sharedConfigProvider.tsx";
import ConversationHeader from "../../features/conversationHeader/ConversationHeader.tsx";
import {selectCurrentBundle} from "../../features/bundles/bundlesSlice.ts";
import {useLazyGetBundleUIQuery} from "../../features/bundles/bundlesAPI.ts";
import {selectProject, selectTenant} from "../../features/chat/chatSettingsSlice.ts";
import {connectChat} from "../../features/chat/chatServiceMiddleware.ts";

const SingleChatApp: React.FC = () => {
    const currentTurn = useAppSelector(selectCurrentTurn);
    const conversationId = useAppSelector(selectConversationId);
    const chatCanvasRef = useRef<HTMLDivElement>(null);
    const [canvasItemLink, setCanvasItemLink] = useState<CanvasItemLink | null>(null);
    const [overrideCanvasItemLink, setOverrideCanvasItemLink] = useState<boolean>(false);
    const tenant = useAppSelector(selectTenant)
    const project = useAppSelector(selectProject)
    const bundleId = useAppSelector(selectCurrentBundle);
    const [trigger, lastArg] = useLazyGetBundleUIQuery()

    useSharedConfigProvider()

    useEffect(() => {
        if (bundleId) {
            trigger({
                tenant,
                project,
                bundleId,
            })
        }
    }, [bundleId, project, tenant, trigger]);

    const bundleUI = useMemo(() => {
        console.log(lastArg)
        if (!bundleId || !lastArg.isSuccess) {
            return null;
        }
        return lastArg.data
    }, [bundleId, lastArg])

    const lastCanvasItem = useMemo(() => {
        if (currentTurn == null) return null;
        const canvasArtifactTypes = getCanvasArtifactTypes()
        const canvasArtifacts = currentTurn.artifacts.filter(artifact => {
            return canvasArtifactTypes.includes(artifact.artifactType);
        })
        return canvasArtifacts.length > 0 ? canvasArtifacts[0] : null;
    }, [currentTurn])

    useEffect(() => {
        setCanvasItemLink(null);
    }, [conversationId]);

    useEffect(() => {
        if (currentTurn) {
            if (!overrideCanvasItemLink && lastCanvasItem && !lastCanvasItem.historical) {
                setCanvasItemLink(getCanvasItemLinkGenerator(lastCanvasItem.artifactType)(lastCanvasItem))
            }
        } else {
            setOverrideCanvasItemLink(false)
        }

    }, [currentTurn, lastCanvasItem, overrideCanvasItemLink]);

    const showItem = useCallback((link: CanvasItemLink | null) => {
        if (currentTurn) {
            setOverrideCanvasItemLink(true);
        }
        setCanvasItemLink(link);
    }, [currentTurn])

    const chatCanvasContextValue = useMemo<ChatCanvasContextValue>(() => {
        return {
            showItem,
            itemLink: canvasItemLink
        }
    }, [canvasItemLink, showItem])

    const chatInterface = useMemo(() => {
        if (lastArg.isUninitialized || lastArg.isLoading) {
            return null
        }

        if (bundleUI) {
            return <div className={"flex-1 flex flex-col h-full"}>
                <iframe
                    srcDoc={bundleUI}
                    className={"w-full h-full border-0"}
                />
            </div>
        }

        return <div className={`flex-1 flex flex-col h-full`}>
            <ConversationHeader/>
            <div className={`flex flex-row flex-1 min-h-0 min-w-0`}>
                <ChatCanvasContext value={chatCanvasContextValue}>
                    <ChatInterface/>
                    <AnimatedExpander contentRef={chatCanvasRef} expanded={!!canvasItemLink}>
                        <ChatCanvas ref={chatCanvasRef}/>
                    </AnimatedExpander>
                </ChatCanvasContext>
            </div>
        </div>
    }, [bundleUI, canvasItemLink, chatCanvasContextValue, lastArg.isLoading, lastArg.isUninitialized])

    const dispatch = useAppDispatch();
    const stayConnected = useAppSelector(selectChatStayConnected)

    useEffect(() => {
        if (!stayConnected)
            dispatch(connectChat())
    }, [dispatch, stayConnected]);


    return useMemo(() => {
        return <div id={SingleChatApp.name}
                    className="flex flex-col h-full w-full min-h-0 min-w-0 bg-slate-100 overflow-hidden">
            <ChatHeader/>

            <div className={`flex flex-row overflow-hidden flex-1 w-full min-h-0 min-w-0`}>
                <ChatSidePanel/>
                {chatInterface}
            </div>
        </div>
    }, [chatInterface])
};

export default SingleChatApp;
