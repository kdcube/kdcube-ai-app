import {WidgetPanelProps} from "../chatSidePanel/ChatSidePanel.tsx";
import {useDispatch} from "react-redux";
import {loadExampleConversation, lockInput, selectTurnOrder, selectTurns, unlockInput} from "../chat/chatStateSlice.ts";
import {ReactNode, useMemo, useState} from "react";
import {pushNotification} from "../popupNotifications/popupsSlice.ts";
import IconContainer from "../../components/IconContainer.tsx";
import {ChevronDown, ChevronUp} from "lucide-react";
import {useAppSelector} from "../../app/store.ts";

interface SectionProps {
    name: string;
    children: ReactNode | ReactNode[];
}

const Section = ({name, children}: SectionProps) => {
    return useMemo(() => {
        return <div className={"flex flex-col p-2 w-full border border-gray-200"}>
            <div>{name}</div>
            <div>
                {children}
            </div>
        </div>
    }, [children, name]);
}

interface CollapsableSectionProps {
    name: string;
    children?: ReactNode | ReactNode[];
}

const CollapsableSection = ({name, children}: CollapsableSectionProps) => {
    const [expanded, setExpanded] = useState(false);
    return useMemo(() => {
        return <div className={"flex flex-col w-full border border-gray-200"}>
            <button className={"flex flex-row cursor-pointer hover:bg-gray-100 p-2"}
                    onClick={() => setExpanded(!expanded)}>
                <span>{name}</span>
                <IconContainer icon={expanded ? ChevronUp : ChevronDown} size={1.5}/>
            </button>
            {expanded && <div className={"p-2"}>
                {children}
            </div>}
        </div>
    }, [children, expanded, name]);
}

interface DebugButtonProps {
    children: ReactNode | ReactNode[];
    onClick: () => void;
}

const DebugButton = ({children, onClick}: DebugButtonProps) => {
    return useMemo(() => {
        return <button
            className={"px-2 py-1 border cursor-pointer hover:bg-gray-100 m-2"}
            onClick={onClick}
        >{children}</button>
    }, [children, onClick])
}

interface TurnProps {
    turnId: string
}

const Turn = ({turnId}: TurnProps) => {
    const turns = useAppSelector(selectTurns);
    const turnData = turns[turnId];
    const [eventTypeFilter, setEventTypeFilter] = useState<string>("");
    const events = useMemo(()=> {
        if (eventTypeFilter.length > 0) {
            return turnData.events.filter((event) => event.eventType.includes(eventTypeFilter));
        }
        return turnData.events;
    }, [eventTypeFilter, turnData.events])

    return useMemo(()=> {
        return <CollapsableSection name={turnId} key={turnId}>
            <CollapsableSection name={"Events"} key={turnId}>
                <div className={"max-h-128 w-full overflow-y-auto"}>
                    <div className={"flex flex-row gap-1 w-full"}>
                        <label>eventType</label>
                        <input type={"text"} className={"border"} value={eventTypeFilter}
                               onChange={(e) => setEventTypeFilter(e.target.value)}/>
                    </div>
                    {events.length ?
                        events.map(((event, i) => {
                            return <div key={i} className={"border p-1 w-full overflow-x-hidden"}>
                                <pre className={"w-full overflow-x-auto"}>{JSON.stringify(event, null, 2)}</pre>
                            </div>
                        })) : <span>No events</span>}
                </div>
            </CollapsableSection>
        </CollapsableSection>
    }, [eventTypeFilter, events, turnId])
}

const TurnListViewer = () => {
    const turnOrder = useAppSelector(selectTurnOrder);

    return useMemo(()=> {
        return <CollapsableSection name={"Turns"}>
            {turnOrder.map(turnId => {
                return <Turn turnId={turnId} key={turnId}/>
            })}
        </CollapsableSection>
    }, [turnOrder])
}

const DebugPanel = ({visible, className}: WidgetPanelProps) => {
    const dispatch = useDispatch();

    return useMemo(()=>{
        return <div className={`w-full ${className ?? ""} ${visible ? "" : "pointer-events-none hidden"} ${className}`}>
            <div className={"flex flex-col w-full h-full overflow-y-auto"}>
                <Section name={"Conversation"}>
                    <DebugButton
                        onClick={() => {
                            dispatch(loadExampleConversation())
                        }}
                    >Load example conversation
                    </DebugButton>
                    <DebugButton
                        onClick={() => {
                            dispatch(lockInput("Input locked via debug menu"))
                        }}
                    >Lock input
                    </DebugButton>
                    <DebugButton
                        onClick={() => {
                            dispatch(unlockInput())
                        }}
                    >Unlock input
                    </DebugButton>
                </Section>
                <Section name={"Notifications"}>
                    <button
                        className={"px-2 py-1 border cursor-pointer hover:bg-gray-100 m-2"}
                        onClick={() => {
                            dispatch(pushNotification({text: "This is an info notification", type: "info"}))
                        }}
                    >Info
                    </button>
                    <button
                        className={"px-2 py-1 border cursor-pointer hover:bg-gray-100 m-2"}
                        onClick={() => {
                            dispatch(pushNotification({text: "This is a warning notification", type: "warning"}))
                        }}
                    >Warning
                    </button>
                    <button
                        className={"px-2 py-1 border cursor-pointer hover:bg-gray-100 m-2"}
                        onClick={() => {
                            dispatch(pushNotification({text: "This is an error notification", type: "error"}))
                        }}
                    >Error
                    </button>
                </Section>
                <TurnListViewer/>
            </div>
        </div>
    }, [className, dispatch, visible])
}

export default DebugPanel;