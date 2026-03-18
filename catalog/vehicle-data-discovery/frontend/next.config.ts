import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable static export for deployment
  output: 'export',

  // Disable trailingSlash to create .html files instead of /index.html directories
  trailingSlash: false,

  // Disable image optimization for static export
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/scene/**',
      },
      // Add your production API domain here once deployed
      // Example: { protocol: 'https', hostname: 'your-domain.com', pathname: '/**' }
    ],
  },
};

export default nextConfig;
