import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

// The platform build invokes:
//   npm install --no-package-lock && OUTDIR=<VI_BUILD_DEST_ABSOLUTE_PATH> npm run build
// so the bundled assets must land in the directory named by OUTDIR.
export default defineConfig({
    plugins: [react()],
    // Relative base so the built index.html + assets work under the widget's
    // mounted path (e.g. /api/integrations/bundles/<tenant>/<project>/<bundle>/...).
    base: "./",
    build: {
        outDir: process.env.OUTDIR || "dist",
        emptyOutDir: true,
    },
});
