import {useMemo} from "react";
import IconContainer from "../../components/IconContainer.tsx";
import {Blocks} from "lucide-react";
import {useSidePanelContext} from "../chatSidePanel/sidePanelContext.ts";
import {getBundleWidgetPanelId} from "../bundles/utils.ts";
import {getLucideIconComponent} from "../../components/DynamicLucideIcon/utils.ts";
import {useGetBundleWidgets} from "../bundles/widgetReducer.tsx";

const BundleControls = () => {
    const sidePanelContext = useSidePanelContext();

    const {currentBundleId, widgets} = useGetBundleWidgets()

    return useMemo(() => {
        if (currentBundleId && widgets.length > 0) {
            return <div className={"flex flex-row items-center gap-1"}>
                {widgets.map((widget) => {
                    const widgetPanelId = getBundleWidgetPanelId(currentBundleId, widget.alias)
                    const Icon = getLucideIconComponent(widget.icon?.lucide ?? null, Blocks);
                    const isActive = widgetPanelId === sidePanelContext.panelId;
                    return <button
                        key={`${currentBundleId}:${widget.alias}`}
                        type={"button"}
                        className={`h-8 w-8 rounded-md border transition-colors flex items-center justify-center ${
                            isActive
                                ? "border-blue-300 bg-blue-50 text-blue-700"
                                : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"
                        }`}
                        title={widget.alias}
                        onClick={() => {
                            sidePanelContext.setPanelId(isActive ? null : widgetPanelId);
                        }}
                    >
                        <IconContainer icon={Icon} size={1.15} className={"stroke-[1.7px]"}/>
                    </button>
                })}
            </div>
        }
        return null
    }, [currentBundleId, widgets, sidePanelContext])
}

export default BundleControls