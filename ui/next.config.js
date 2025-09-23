/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true
  },
  webpack: (config) => {
    config.externals = config.externals || [];
    config.externals.push('sharp');
    return config;
  }
}

module.exports = nextConfig
