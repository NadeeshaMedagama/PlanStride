const appUrl = import.meta.env.VITE_APP_URL;
const siteUrl = import.meta.env.VITE_SITE_URL;
if (!appUrl || !siteUrl) {
  throw new Error(
    "VITE_APP_URL and VITE_SITE_URL must be set in .env.development / .env.production"
  );
}

export const SITE_URL = siteUrl.replace(/\/$/, "");
export const SIGNUP_URL = `${appUrl}/signup`;
export const LOGIN_URL = `${appUrl}/login`;
