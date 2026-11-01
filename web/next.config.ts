import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  devIndicators: false,
  agentRules: false,
  turbopack: { root: process.cwd() },
};

export default nextConfig;
