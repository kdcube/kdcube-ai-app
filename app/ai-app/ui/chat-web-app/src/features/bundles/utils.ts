export const getBundleWidgetPanelId = (bundleId:string, widgetId: string) => {
    return `dynamic_bundle_widget_${bundleId}_${widgetId}`;
}