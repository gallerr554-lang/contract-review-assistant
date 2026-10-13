import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("@element-plus/icons-vue")) return "vendor-icons";
          if (id.includes("element-plus")) return "vendor-element-plus";
          if (id.includes("@floating-ui")) return "vendor-floating-ui";
          if (id.includes("async-validator")) return "vendor-validation";
          if (id.includes("dayjs")) return "vendor-dayjs";
          if (id.includes("axios")) return "vendor-axios";
          if (id.includes("vue") || id.includes("pinia")) return "vendor-vue";
          return "vendor";
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
