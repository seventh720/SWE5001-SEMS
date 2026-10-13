import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
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
        target: "http://localhost:18080",
        changeOrigin: true,
      },
      "/actuator": {
        target: "http://localhost:18080",
        changeOrigin: true,
      },
    },
  },
});
