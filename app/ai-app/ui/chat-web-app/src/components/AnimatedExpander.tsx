import {ReactNode, RefObject, useEffect, useMemo, useRef, useState} from "react";
import {motion} from "motion/react";

interface AnimatedExpanderProps {
    contentRef: RefObject<Element | null>;
    children: ReactNode | ReactNode[];
    expanded?: boolean
    className?: string
    direction?: "horizontal" | "vertical" | "both"
}

const AnimatedExpander = ({
                              contentRef,
                              children,
                              className,
                              direction = "horizontal",
                              expanded = true
                          }: AnimatedExpanderProps) => {
    const [contentSize, setContentSize] = useState({width: 0, height: 0});

    const wasExpanded = useRef(expanded);
    const [animating, setAnimating] = useState(true);

    useEffect(() => {
        if (wasExpanded.current !== expanded) {
            setAnimating(true);
        }
        wasExpanded.current = expanded;
    }, [expanded]);

    useEffect(() => {
        const observer = new ResizeObserver(() => {
            if (contentRef.current) {
                const rect = contentRef.current.getBoundingClientRect()
                setContentSize({width: rect.width, height: rect.height});
            }
        })
        if (contentRef.current) {
            observer.observe(contentRef.current)
        } else {
            console.warn("no content ref")
        }
        return () => {
            observer.disconnect()
        }
    }, [contentRef]);

    return useMemo(() => {
        const zero = {} as Record<string, number | string>;
        const content = {} as Record<string, number | string>;

        if (direction === "horizontal" || direction === "both") {
            zero.width = 0
            content.width = contentSize.width;
        }

        if (direction === "vertical" || direction === "both") {
            zero.height = 0
            content.height = contentSize.height;
        }

        return <motion.div
            className={`overflow-hidden ${className ?? ""}`}
            initial={expanded ? zero : content}
            animate={expanded ? content : zero}
            transition={animating ? undefined : {duration: 0}}
            onAnimationComplete={() => {
                if (animating) {
                    setAnimating(false)
                }
            }}
        >
            {children}
        </motion.div>
    }, [direction, className, expanded, animating, children, contentSize.width, contentSize.height]);
}

export default AnimatedExpander;