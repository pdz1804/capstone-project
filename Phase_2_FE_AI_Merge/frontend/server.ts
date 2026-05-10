import express from "express";
import { createServer as createViteServer } from "vite";
import http from "http";
import https from "https";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, ".env") });

function normalizeProxyTarget(rawTarget?: string): URL {
  const fallback = rawTarget?.trim() || "http://127.0.0.1:5001";
  const normalized = fallback.endsWith("/api") ? fallback.slice(0, -4) : fallback;
  return new URL(normalized);
}

async function startServer() {
  const app = express();
  // Default 5173 — port 3000 is often taken by Bolt/Next/other tools; wrong tab = "not our UI".
  const PORT = Number(process.env.PORT || process.env.FE_PORT || 5173);
  const projectRoot = __dirname;
  const apiProxyTarget = normalizeProxyTarget(
    process.env.API_PROXY_TARGET || process.env.VITE_API_PROXY_TARGET
  );

  app.use("/api", (req, res) => {
    const client = apiProxyTarget.protocol === "https:" ? https : http;
    const upstreamReq = client.request(
      {
        protocol: apiProxyTarget.protocol,
        hostname: apiProxyTarget.hostname,
        port: apiProxyTarget.port,
        method: req.method,
        path: req.originalUrl,
        headers: {
          ...req.headers,
          host: apiProxyTarget.host,
        },
      },
      (upstreamRes) => {
        res.status(upstreamRes.statusCode || 502);
        Object.entries(upstreamRes.headers).forEach(([key, value]) => {
          if (value !== undefined) {
            res.setHeader(key, value);
          }
        });
        upstreamRes.pipe(res);
      }
    );

    upstreamReq.on("error", (error) => {
      res.status(502).json({
        detail: `API proxy could not reach ${apiProxyTarget.origin}${req.originalUrl}`,
        error: error.message,
      });
    });

    req.pipe(upstreamReq);
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
    console.log(`API proxy target → ${apiProxyTarget.origin}`);
    console.log(`If you see a different product (e.g. Bolt), you opened the wrong port or another app is running.`);
    console.log("");
  });
}

startServer();
