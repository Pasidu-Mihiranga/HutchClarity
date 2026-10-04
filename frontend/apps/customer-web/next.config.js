/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: [
    "@clarity/ui",
    "@clarity/sdk",
    "@clarity/i18n",
    "@clarity/widget",
  ],
  reactStrictMode: true,
};

module.exports = nextConfig;
