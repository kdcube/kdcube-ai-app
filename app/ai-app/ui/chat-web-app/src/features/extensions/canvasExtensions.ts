import {ComponentType, RefObject} from "react";
import {UnknownArtifact} from "../chat/chatTypes.ts";
import {CanvasItemLink} from "../canvas/canvasContext.tsx";
import {IconType} from "../../components/IconContainer.tsx";

export type ArtifactComponentProps = {
    item: UnknownArtifact
    contentRef: RefObject<HTMLDivElement | null>
}

export type ArtifactLinkGenerator = (artifact: UnknownArtifact) => CanvasItemLink
export type ArtifactComponent = ComponentType<ArtifactComponentProps>
export type ArtifactLinkComparator = (link: CanvasItemLink, artifact: UnknownArtifact) => boolean
export type ArtifactTitleGenerator = (artifact: UnknownArtifact) => string
export type ArtifactIconGenerator = (artifact: UnknownArtifact) => IconType | null
export type ArtifactCopyHandler = (artifact: UnknownArtifact, contentRef?: RefObject<HTMLDivElement | null> | null) => void
export type ArtifactSaveHandler = (artifact: UnknownArtifact, contentRef?: RefObject<HTMLDivElement | null> | null) => void


export interface CanvasExtension {
    component: ArtifactComponent
    linkGenerator: ArtifactLinkGenerator
    linkComparator: ArtifactLinkComparator
    titleGenerator: ArtifactTitleGenerator
    iconGenerator?: ArtifactIconGenerator | null
    copyHandler?: ArtifactCopyHandler | null
    saveHandler?: ArtifactSaveHandler | null
}

const canvasExtensions: Record<string, CanvasExtension> = {}

export const addCanvasItemExtension = (
    artifactType: string,
    config: CanvasExtension
) => {
    canvasExtensions[artifactType] = config
}

export const isCanvasArtifactType = (artifactType: string) => {
    return !!canvasExtensions[artifactType]
}

export const getCanvasArtifactTypes = () => {
    return Object.keys(canvasExtensions)
}

export const getCanvasItemComponent = (artifactType: string): ArtifactComponent => {
    return canvasExtensions[artifactType].component;
}

export const getCanvasItemLinkGenerator = (artifactType: string): ArtifactLinkGenerator => {
    return canvasExtensions[artifactType].linkGenerator;
}

export const getArtifactLinkComparator = (artifactType: string): ArtifactLinkComparator => {
    return canvasExtensions[artifactType].linkComparator;
}

export const getArtifactTitleGenerator = (artifactType: string): ArtifactTitleGenerator => {
    return canvasExtensions[artifactType].titleGenerator;
}

export const getArtifactIconGenerator = (artifactType: string): ArtifactIconGenerator | undefined | null => {
    return canvasExtensions[artifactType].iconGenerator;
}

export const getArtifactCopyHandler = (artifactType: string): ArtifactCopyHandler | undefined | null => {
    return canvasExtensions[artifactType].copyHandler;
}

export const getArtifactSaveHandler = (artifactType: string): ArtifactSaveHandler | undefined | null => {
    return canvasExtensions[artifactType].saveHandler;
}