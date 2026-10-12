/// <reference types="vite/client" />

// Public build-time config. Vite inlines `VITE_`-prefixed vars from .env;
// declaring them here keeps `import.meta.env` typed under
// `noPropertyAccessFromIndexSignature`.
interface ImportMetaEnv {
  // Where this site is served (absolute URLs for Open Graph tags).
  readonly VITE_SITE_URL: string;
  // The product app, where "Get started" and "Sign in" lead.
  readonly VITE_APP_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
