import type { NextConfig } from "next";

/** Server-side proxy target for `/api/*` and `/health` (local or Railway). */
const apiProxyTarget = (
  process.env.API_PROXY_TARGET ||
  process.env.BACKEND_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${apiProxyTarget}/health`,
      },
    ];
  },
};

export default nextConfig;
