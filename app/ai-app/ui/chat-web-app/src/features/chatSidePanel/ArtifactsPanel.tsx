import {ReactNode, useMemo} from "react";
import {useAppSelector} from "../../app/store.ts";
import {selectTurnOrder, selectTurns} from "../chat/chatStateSlice.ts";
import {getArtifactTitleGenerator, isCanvasArtifactType} from "../extensions/canvasExtensions.ts";
import {motion} from "motion/react";
import {truncateWords} from "../../utils/textTruncate.ts";
import IconContainer from "../../components/IconContainer.tsx";
import {MessageSquareMore} from "lucide-react";


interface ArtifactsPanelProps {
    visible?: boolean;
    className?: string;
}

export const ArtifactsPanel = ({className, visible = true}: ArtifactsPanelProps) => {
    const turnOrder = useAppSelector(selectTurnOrder);
    const turns = useAppSelector(selectTurns);

    const canvasArtifactsMemo = useMemo(() => {
        return turnOrder.reduce((acc, turnId) => {
            const turn = turns[turnId];
            const artifacts = turn.artifacts;
            const canvasArtifacts = artifacts.filter((artifact) => {
                return isCanvasArtifactType(artifact.artifactType)
            });
            if (canvasArtifacts.length > 0) {
                acc.push(
                    <div key={turnId} className={"w-full p-2"}>
                        <button className={"flex flex-row items-center justify-center text gap-1 "}>
                            <IconContainer icon={MessageSquareMore} size={1.5} className={"translate-y-px"}/>
                            <h3 className={"truncate text-xl"}>{truncateWords(turn.userMessage.text, 50) }</h3>
                        </button>
                        <div className={"ml-0.5 w-full flex flex-col"}>
                            {canvasArtifacts.map((artifact) => {
                                const title = getArtifactTitleGenerator(artifact.artifactType)(artifact);
                                return <div>{title}</div>;
                            })}
                        </div>
                    </div>
                );
            }
            return acc;
        }, [] as ReactNode[])
    }, [turnOrder, turns])

    const panelContent = useMemo(() => {
        return <div className={"w-full h-full"}>
            {canvasArtifactsMemo.length
                ?
                canvasArtifactsMemo
                :
                <div className={""}>
                    No artifacts
                </div>
            }
        </div>
    }, [canvasArtifactsMemo])

    return useMemo(() => {
        return <motion.div
            className={`${className} ${visible ? "" : "pointer-events-none"}`}
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