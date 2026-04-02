import {ReactNode, useCallback, useMemo, useRef, useState} from "react";
import {
    ArrowLeftRight,
    Bot,
    Bug,
    CircleDollarSign,
    CirclePlus,
    CreditCard,
    Database,
    MessageSquareMore,
    MessagesSquare,
    SlidersHorizontal
} from "lucide-react";
import IconContainer from "../../components/IconContainer.tsx";
import AnimatedExpander from "../../components/AnimatedExpander.tsx";
import {useAppDispatch, useAppSelector} from "../../app/store.ts";
import {newConversation} from "../chat/chatStateSlice.ts";
import {showDebugControls} from "../../BuildConfig.ts";
import DebugPanel from "../debugPanel/DebugPanel.tsx";
import ResizableContainer from "../../components/ResizableContainer.tsx";
import {readParam, writeParam} from "../settingsStorage/settingsStorage.ts";
import {selectAppUser} from "../auth/authSlice.ts";
import {ConversationsPanel} from "./ConversationsPanel.tsx";
import {
    AIBundlesPanel,
    ConvBrowserPanel,
    EconomicsPanel,
    EconomicUsagePanel,
    GatewayPanel,
    RedisBrowserPanel, VersatilePreferencesPanel
} from "./GenericPanels.tsx";

interface MenuButtonProps {
    children: ReactNode | ReactNode[];
    onClick?: () => void;
}

const MenuButton = ({children, onClick}: MenuButtonProps) => {
    return useMemo(() => {
        return <button
            onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                onClick?.()
            }}
            className={"hover:bg-gray-200 transition-all duration-200 p-1 rounded-md cursor-pointer"}>
            {children}
        </button>
    }, [children, onClick])
}

export interface WidgetPanelProps {
    visible: boolean;
    className?: string;
}

type Panels =
    "conversations"
    | "economics"
    | "ai_bundles"
    | "gateway"
    | "conv_browser"
    | "redis_browser"
    | "economic_usage"
    | "versatile_preferences"
    | "debug"
    | null

const ChatSidePanel = () => {
    const dispatch = useAppDispatch();

    const parentRef = useRef<HTMLDivElement>(null);
    const [visiblePanel, setVisiblePanel] = useState<Panels>(null);
    const sidePanelContentRef = useRef<HTMLDivElement>(null);

    const onPanelButtonClick = useCallback((panel: Panels) => {
        if (panel === null || panel !== visiblePanel) {
            setVisiblePanel(panel)
        } else {
            setVisiblePanel(null)
        }
    }, [visiblePanel])

    const user = useAppSelector(selectAppUser)

    const onPanelResize = useCallback((size: number) => {
        writeParam("sidePanelWidth", size, user ? user.username : null);
    }, [user])

    return useMemo(() => {

        const initialPanelWidth = readParam("sidePanelWidth", 400) as number

        return <div
            ref={parentRef}
            className={"flex flex-row h-full overflow-visible min-h-0 min-w-0"}>
            <div
                className={"h-full flex flex-col items-center bg-gray-50 border-r border-gray-200 pt-1 px-1 text-gray-700 gap-1"}>
                <MenuButton onClick={() => dispatch(newConversation())}>
                    <IconContainer icon={CirclePlus} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("conversations");
                    }}
                >
                    <IconContainer icon={MessagesSquare} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("economics");
                    }}
                >
                    <IconContainer icon={CircleDollarSign} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("economic_usage");
                    }}
                >
                    <IconContainer icon={CreditCard} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("ai_bundles");
                    }}
                >
                    <IconContainer icon={Bot} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("gateway");
                    }}
                >
                    <IconContainer icon={ArrowLeftRight} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("conv_browser");
                    }}
                >
                    <IconContainer icon={MessageSquareMore} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("redis_browser");
                    }}
                >
                    <IconContainer icon={Database} size={1.5}/>
                </MenuButton>
                <MenuButton
                    onClick={() => {
                        onPanelButtonClick("versatile_preferences");
                    }}
                >
                    <IconContainer icon={SlidersHorizontal} size={1.5}/>
                </MenuButton>
                {showDebugControls && <MenuButton
                    onClick={() => {
                        onPanelButtonClick("debug");
                    }}
                >
                    <IconContainer icon={Bug} size={1.5}/>
                </MenuButton>}
            </div>
            {/*<div className={"absolute h-full top-0 left-12 z-20 shadow-md border-r border-gray-200 bg-white"}>*/}
            <div
                className={`h-full border-r border-gray-200 bg-white relative ${visiblePanel ? "pointer-events-auto" : "pointer-events-none"}`}>
                <AnimatedExpander contentRef={sidePanelContentRef} className={"h-full"}
                                  expanded={visiblePanel !== null}>
                    {/*<div className={"h-full"} ref={sidePanelContentRef} style={{width: `${panelWidth}px`}}>*/}
                    <ResizableContainer ref={sidePanelContentRef} onResize={onPanelResize}
                                        initialSize={initialPanelWidth} minSize={300} className={"h-full"}>
                        <ConversationsPanel visible={visiblePanel === "conversations"}
                                            className={"w-full h-full absolute left-0 top-0"}/>
                        <EconomicsPanel visible={visiblePanel === "economics"}
                                        className={"w-full h-full absolute left-0 top-0"}/>
                        <AIBundlesPanel visible={visiblePanel === "ai_bundles"}
                                        className={"w-full h-full absolute left-0 top-0"}/>
                        <GatewayPanel visible={visiblePanel === "gateway"}
                                      className={"w-full h-full absolute left-0 top-0"}/>
                        <ConvBrowserPanel visible={visiblePanel === "conv_browser"}
                                          className={"w-full h-full absolute left-0 top-0"}/>
                        <RedisBrowserPanel visible={visiblePanel === "redis_browser"}
                                           className={"w-full h-full absolute left-0 top-0"}/>
                        <EconomicUsagePanel visible={visiblePanel === "economic_usage"}
                                            className={"w-full h-full absolute left-0 top-0"}/>
                        <VersatilePreferencesPanel visible={visiblePanel === "versatile_preferences"}
                                                   className={"w-full h-full absolute left-0 top-0"}/>
                        {showDebugControls && <DebugPanel visible={visiblePanel === "debug"}
                                                          className={"w-full h-full absolute left-0 top-0"}/>}
                    </ResizableContainer>
                    {/*</div>*/}
                </AnimatedExpander>
            </div>
        </div>
    }, [dispatch, onPanelButtonClick, onPanelResize, visiblePanel])
}

export default ChatSidePanel;
