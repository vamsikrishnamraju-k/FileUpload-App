const express = require("express");
const path = require("path");
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://backend-service.backend:5000";
const DIST_DIR = path.join(__dirname, "dist");

app.use(
  "/api",
  createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    on: {
      proxyReq: (proxyReq, req) => {
        console.log(JSON.stringify({
          level: "INFO",
          service: "file-upload-react-frontend",
          action: "api_request",
          method: req.method,
          path: req.originalUrl
        }));
      },
      proxyRes: (proxyRes, req) => {
        console.log(JSON.stringify({
          level: proxyRes.statusCode >= 400 ? "ERROR" : "INFO",
          service: "file-upload-react-frontend",
          action: "api_response",
          method: req.method,
          path: req.originalUrl,
          status: proxyRes.statusCode
        }));
      },
      error: (err, req, res) => {
        console.log(JSON.stringify({
          level: "ERROR",
          service: "file-upload-react-frontend",
          action: "proxy_error",
          path: req.originalUrl,
          error: err.message
        }));
        if (!res.headersSent) res.status(502).json({ error: "Backend unavailable" });
      }
    }
  })
);

app.use(express.static(DIST_DIR));

app.get("*", (req, res) => {
  res.sendFile(path.join(DIST_DIR, "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({
    level: "INFO",
    service: "file-upload-react-frontend",
    message: "React frontend started",
    port: PORT,
    backend: BACKEND_URL
  }));
});
