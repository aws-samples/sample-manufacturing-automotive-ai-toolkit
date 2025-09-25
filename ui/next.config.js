/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true
  },
  webpack: (config) => {
    config.externals = config.externals || [];
    config.externals.push('sharp');
    return config;
  },
  server: {
    host: '0.0.0.0',
    port: 3000
  }
}

module.exports = nextConfig
