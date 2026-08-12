import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Vite's dev server only accepts requests whose Host header it
    // recognizes (anti DNS-rebinding). A leading "." allows the domain
    // itself plus every subdomain, which covers ngrok's random per-session
    // hostname (e.g. freckled-stinky-broadness.ngrok-free.dev) without
    // needing to update this every time you restart a tunnel. Only affects
    // `vite dev`/`vite preview` — irrelevant to the nginx-served production
    // build (frontend/Dockerfile), which doesn't run Vite's server at all.
    allowedHosts: [".ngrok-free.dev", ".ngrok-free.app", ".ngrok.app", ".ngrok.io"],
  },
});
