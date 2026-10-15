import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, process.cwd(), "").API_PROXY_TARGET || "http://localhost:18080";
  return {
  plugins: [react()],
  test: {
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts"],
      reporter: ["text", "html", "json-summary", "lcov"],
      reportsDirectory: "coverage",
    },
  },
  server: {
    port: 15173,
    strictPort: true,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
      },
      "/actuator": {
        target,
        changeOrigin: true,
      },
    },
  },
  };
});
