import {useAppSelector} from "../app/store.ts";
import {selectPlatformVersion} from "../features/chat/chatSettingsSlice.ts";

const PlatformVersionBadge = () => {
    const version = useAppSelector(selectPlatformVersion);
    if (!version) return null;

    return (
        <div
            className="fixed bottom-1 right-2 z-50 pointer-events-none select-none text-[11px] text-gray-400 opacity-60"
            title={`Platform ${version}`}
        >
            {version}
        </div>
    );
};

export default PlatformVersionBadge;
