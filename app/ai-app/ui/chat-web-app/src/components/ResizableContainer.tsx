import {
    CSSProperties,
    MouseEvent,
    ReactNode,
    RefObject,
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState
} from "react";

interface ResizableContainerProps {
    className?: string;
    children?: ReactNode | ReactNode[];
    position?: "top" | "bottom" | "left" | "right";
    initialSize?: number;
    minSize?: number;
    ref?: RefObject<HTMLDivElement | null>
    onResize?: (size:number) => void;
}

const ResizableContainer = ({children, className, ref, onResize, initialSize = 200, minSize = 100, position = "right"}: ResizableContainerProps) => {
    const contentContainerRef = useRef<HTMLDivElement | null>(null);

    const [isResizing, setIsResizing] = useState(false);
    const [containerSize, setContainerSize] = useState<number>(Math.max(initialSize, minSize));

    useEffect(() => {
        const resize = (e: globalThis.MouseEvent) => {
            if (!contentContainerRef.current) return;
            let newSize = minSize;
            switch (position) {
                case "top":
                    newSize = e.clientY - contentContainerRef.current.getBoundingClientRect().bottom;
                    break;
                case "bottom":
                    newSize = e.clientY - contentContainerRef.current.getBoundingClientRect().top;
                    break;
                case "left":
                    newSize = e.clientX - contentContainerRef.current.getBoundingClientRect().right;
                    break;
                case "right":
                    newSize = e.clientX - contentContainerRef.current.getBoundingClientRect().left;
                    break;
            }
            newSize = Math.max(newSize, minSize);
            setContainerSize(newSize)
            onResize?.(newSize)
        }

        const stopResize = () => {
            setIsResizing(false);
        }

        if (isResizing) {
            window.addEventListener('mousemove', resize);
            window.addEventListener('mouseup', stopResize);
        }

        return () => {
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResize);
        };
    }, [isResizing, minSize, onResize, position]);

    const onMouseDown = useCallback((e: MouseEvent) => {
        e.preventDefault();
        setIsResizing(true)
    }, [])

    const onMouseUp = useCallback((e: MouseEvent) => {
        e.preventDefault();
        setIsResizing(true)
    }, [])

    return useMemo(() => {
        const containerStyle: CSSProperties = {}

        if (position === "top" || position === "bottom") {
            containerStyle.height = containerSize + "px";
        } else {
            containerStyle.width = containerSize + "px";
        }

        let resizeLine = null
        switch (position) {
            case "top":
                resizeLine = <div className={"w-full absolute top-0 h-2 cursor-row-resize translate-y-1"}>&nbsp;</div>;
                break;
            case "bottom":
                resizeLine =
                    <div className={"w-full absolute bottom-0 h-2 cursor-row-resize -translate-y-1"}>&nbsp;</div>;
                break;
            case "left":
                resizeLine =
                    <div className={"h-full absolute left-0 w-2 cursor-col-resize -translate-x-1"}>&nbsp;</div>;
                break;
            case "right":
                resizeLine = <div
                    className={"h-full absolute right-0 w-2 cursor-col-resize translate-x-1 hover:bg-gray-200"}
                    onMouseDown={onMouseDown}
                    onMouseUp={onMouseUp}
                >&nbsp;</div>;
                break;
        }

        return <div className={`relative ${className ?? ""}`} ref={ref} style={containerStyle}>
            <div className={"h-full w-full"} ref={contentContainerRef}>
                {children}
                {resizeLine}
            </div>
        </div>
    }, [children, className, containerSize, onMouseDown, onMouseUp, position, ref])
}

export default ResizableContainer;