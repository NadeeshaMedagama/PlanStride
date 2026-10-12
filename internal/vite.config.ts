import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// SPA: no server rendering of routes. The build prerenders the document shell
// once to `dist/client/_shell.html`; the host serves that file for every path
// (see `public/_redirects`) and the router takes over on the client.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  // The API only accepts requests from the origins in its CORS_ORIGINS, so the
  // port is fixed: if 3002 is taken, fail loudly rather than quietly moving to
  // a port every sign-in request is refused on.
  server: { port: 3002, strictPort: true },
  plugins: [
    tailwindcss(),
    tanstackStart({ spa: { enabled: true } }),
    viteReact(),
  ],
});
