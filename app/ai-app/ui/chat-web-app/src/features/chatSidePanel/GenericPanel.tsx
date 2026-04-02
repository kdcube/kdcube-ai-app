import {useEffect, useMemo, useRef} from "react";
import {useAppSelector} from "../../app/store.ts";
import {selectProject, selectTenant} from "../chat/chatSettingsSlice.ts";
import {motion} from "motion/react";
import {GetWidgetParams} from "../widgetPanels/widgetPanels.ts";
import IconContainer from "../../components/IconContainer.tsx";
import {LoaderCircle} from "lucide-react";

interface IFrameSrcDocPanelProps {
    visible: boolean;
    srcDoc: string;
    className?: string;
}

const IFrameSrcDocPanel = ({visible, srcDoc, className}: IFrameSrcDocPanelProps) => {
    return useMemo(() => {
        return <motion.div
            className={className}
            style={{
                pointerEvents: visible ? "auto" : 'none',
            }}
            initial={{
                opacity: visible ? 0 : 1,
            }}
            animate={{
                opacity: visible ? 1 : 0,
            }}
        >
            <div className={"w-full h-full flex flex-col"}>
                <iframe
                    srcDoc={srcDoc}
                    className={"w-full h-full border-0"}
                />
            </div>
        </motion.div>
    }, [className, srcDoc, visible])
}

interface PanelLoadingProps {
    className?: string;
}

const PanelLoading = ({className}: PanelLoadingProps) => {
    return useMemo(() => {
        return <div className={className}>
            <div className={"w-full h-full flex text-gray-200"}>
                <IconContainer icon={LoaderCircle} className={"animate-spin duration-200"} containerClassName={"m-auto"}
                               size={4}/>
            </div>
        </div>
    }, [className])
}

interface PanelErrorProps {
    className?: string;
}

const PanelLoadingError = ({className}: PanelErrorProps) => {
    return useMemo(() => {
        return <div className={className}>
            <div className={"w-full h-full flex text-gray-600 p-2"}>
                <div>Sorry, an error has occurred</div>
            </div>
        </div>
    }, [className])
}

interface GenericWidgetPanelProps {
    visible: boolean;
    className?: string;
    trigger: (params: GetWidgetParams, preferCache?: boolean) => void;
    reloadOnShow?: boolean;
    lastArg: {
        data?: string | undefined;
        isFetching: boolean;
        isError: boolean;
        isUninitialized: boolean;
    }
}

export const GenericPanel = ({visible, className, trigger, lastArg, reloadOnShow}: GenericWidgetPanelProps) => {
    const wasVisible = useRef(visible);

    const {data, isFetching, isError, isUninitialized} = useMemo(() => {
        return lastArg
    }, [lastArg]);

    const tenant = useAppSelector(selectTenant);
    const project = useAppSelector(selectProject);

    useEffect(() => {
        if (!wasVisible.current && reloadOnShow && visible) {
            trigger({tenant, project}, false);
        } else if (visible && isUninitialized) {
            trigger({tenant, project}, true)
        }
        wasVisible.current = visible;
    }, [isUninitialized, project, reloadOnShow, tenant, trigger, visible]);

    return useMemo(() => {
        if (visible) {
            if (isFetching) {
                return <PanelLoading className={className}/>
            }
            if (isError) {
                return <PanelLoadingError className={className}/>
            }
        }

        if (!isFetching && !isError) {
            return <IFrameSrcDocPanel visible={visible} className={className} srcDoc={data as string}/>
        }

        return null
    }, [className, data, isError, isFetching, visible])
}