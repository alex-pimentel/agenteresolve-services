/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the AI services gateway. */
  readonly VITE_API_BASE?: string;
  /** Optional Clerk publishable key; the UI degrades gracefully without it. */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  /** Standalone Louder app URL surfaced by the /louder route. */
  readonly VITE_LOUDER_URL?: string;
  /** Standalone QR Code app URL surfaced by the /qrcode route. */
  readonly VITE_QRCODE_URL?: string;
  /** Standalone Imposition app URL surfaced by the /imposition route. */
  readonly VITE_IMPOSITION_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
