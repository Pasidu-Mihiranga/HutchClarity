/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@clarity/ui", "@clarity/sdk", "@clarity/i18n"],
  reactStrictMode: true,
};

module.exports = nextConfig;
