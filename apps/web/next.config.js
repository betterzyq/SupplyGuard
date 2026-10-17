/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.SUPPLYGUARD_NEXT_DIST_DIR || ".next",
  typescript: {
    tsconfigPath: process.env.SUPPLYGUARD_TSCONFIG || "tsconfig.json",
  },
  experimental: { cpus: 2 },
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
      { source: "/health/:path*", destination: `${backend}/health/:path*` },
    ];
  },
};

module.exports = nextConfig;
