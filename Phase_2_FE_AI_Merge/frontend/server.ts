import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  // Default 5173 — port 3000 is often taken by Bolt/Next/other tools; wrong tab = "not our UI".
  const PORT = Number(process.env.PORT || process.env.FE_PORT || 5173);
  const projectRoot = __dirname;

  app.use(express.json());

  // API Routes
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok" });
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      root: projectRoot,
      configFile: path.join(projectRoot, "vite.config.ts"),
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(projectRoot, "dist");
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log("");
    console.log(`BK-MInD frontend (Phase_2_FE_AI_Merge) → http://localhost:${PORT}`);
    console.log(`If you see a different product (e.g. Bolt), you opened the wrong port or another app is running.`);
    console.log("");
  });
}

startServer();
