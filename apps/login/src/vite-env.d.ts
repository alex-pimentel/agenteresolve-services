/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the AI services gateway. */
  readonly VITE_API_BASE?: string;
  /** REQUIRED here: Clerk publishable key for the central sign-in. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  /** Extra redirect origins (comma-separated) besides *.agenteresolve.com.br. */
  readonly VITE_ALLOWED_REDIRECT_ORIGINS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
