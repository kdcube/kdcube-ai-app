import {useAppDispatch, useAppSelector} from "../../app/store.ts";
import {
    selectConversationDescriptors,
    selectConversationDescriptorsLoading,
    selectConversationDescriptorsLoadingError
} from "../conversations/conversationsSlice.ts";
import {useEffect, useMemo, useState} from "react";
import {timeSortPredicate} from "../../utils/utils.ts";
import {selectCurrentBundle} from "../bundles/bundlesSlice.ts";
import {deleteConversation, loadConversationList} from "../conversations/conversationsMiddleware.ts";
import {motion} from "motion/react";
import IconContainer from "../../components/IconContainer.tsx";
import {Search, Trash2} from "lucide-react";
import {ConversationDescriptor} from "../conversations/conversationsTypes.ts";
import {useNavigate} from "react-router-dom";
import {getChatPagePath} from "../chat/configHelper.ts";
import {formatDateToLocalString} from "../../utils/dateTimeUtils.ts";

interface ConversationMenuItemProps {
    conversation: ConversationDescriptor;
}

const ConversationMenuItem = ({conversation}: ConversationMenuItemProps) => {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();

    return useMemo(() => {
        const href = getChatPagePath() + "/" + conversation.id;
        return <div
            className={"group flex flex-row mx-2.5 mt-2 px-2 py-1 text-md hover:bg-gray-100 rounded-md cursor-pointer"}>
            <a
                href={href}
                onClick={e => {
                    e.preventDefault();
                    e.stopPropagation();
                    navigate(href)
                }}
            >
                <p>{conversation.title ?? "Unnamed conversation"}</p>
                {conversation.lastActivity && (<p className={"text-sm"}>
                    {formatDateToLocalString(new Date(conversation.lastActivity))}
                </p>)}
            </a>
            <button
                className={"group-hover:block hidden ml-auto text-gray-600 hover:text-gray-800 cursor-pointer"}
                onClick={(e) => {
                    e.preventDefault();
                    dispatch(deleteConversation(conversation.id));
                }}
            ><IconContainer icon={Trash2} size={1.3}
            /></button>
        </div>
    }, [conversation.id, conversation.lastActivity, conversation.title, dispatch, navigate]);
}

interface ConversationsPanelProps {
    visible: boolean;
    className?: string;
}

export const ConversationsPanel = ({visible, className}: ConversationsPanelProps) => {
    const dispatch = useAppDispatch();
    const conversations = useAppSelector(selectConversationDescriptors);

    const processedConversations = useMemo(() => {
        return conversations ? conversations.concat().sort((a, b) => timeSortPredicate(a.lastActivity, b.lastActivity)).reverse() : null;

    }, [conversations]);

    const conversationsLoading = useAppSelector(selectConversationDescriptorsLoading);
    const conversationsLoadingError = useAppSelector(selectConversationDescriptorsLoadingError);

    const [searchFor, setSearchFor] = useState("");

    const currentBundle = useAppSelector(selectCurrentBundle);

    useEffect(() => {
        if (currentBundle && visible) {
            dispatch(loadConversationList())
        }
    }, [currentBundle, dispatch, visible]);

    const panelContent = useMemo(()=>{
        return <div className={"w-full h-full flex flex-col"}>
            <h1 className={"text-xl mx-auto mt-2 ml-2.5"}>Conversations</h1>
            {conversationsLoading && !conversations && (
                <div>loading</div>
            )}
            {conversationsLoadingError && (
                <div>error</div>
            )}
            {processedConversations && processedConversations.length > 0 && (
                <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
                    <div
                        className="p-1.5 mx-2 border bg-white border-gray-200 transition-all rounded-md flex flex-row items-center focus-within:border-gray-800">
                        <IconContainer icon={Search} size={1}/>
                        <input name={"convSearch"} type={"text"}
                               className={"flex-1 ml-2 focus:outline-none"}
                               placeholder={"Search"} value={searchFor}
                               onChange={e => setSearchFor(e.target.value)}/>
                    </div>
                    <div className={"flex-1 min-h-0 overflow-y-auto mr-2 mt-1 mb-2"}>
                        {processedConversations.map((conversation) => (
                            <ConversationMenuItem conversation={conversation} key={conversation.id}/>
                        ))}
                    </div>
                </div>
            )}
        </div>
    }, [conversations, conversationsLoading, conversationsLoadingError, processedConversations, searchFor])

    return useMemo(() => {
        return <motion.div
            className={className}
            initial={{
                opacity: visible ? 0 : 1,
            }}
            animate={{
                opacity: visible ? 1 : 0,
            }}
        >
            {panelContent}
        </motion.div>
    }, [className, visible, panelContent])
}