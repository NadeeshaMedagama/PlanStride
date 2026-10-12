import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Static site: every route is prerendered to HTML at build time and the
// output under `dist/` deploys as plain files to a CDN. `crawlLinks` follows
// internal links from the rendered pages, so new routes linked from an
// existing page are picked up without touching this config.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  // Fixed like the other front ends: the canonical and Open Graph URLs
  // (VITE_SITE_URL) assume 3000, so a taken port is an error, not a new port.
  server: { port: 3000, strictPort: true },
  plugins: [
    tailwindcss(),
    tanstackStart({
      prerender: { enabled: true, crawlLinks: true, failOnError: true },
      pages: [{ path: "/" }],
    }),
    viteReact(),
  ],
});
