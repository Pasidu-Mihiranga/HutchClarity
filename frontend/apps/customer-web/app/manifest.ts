import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Hutch Clarity",
    short_name: "Clarity",
    description: "Understand and fix prepaid balance changes",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#f26226",
    lang: "en",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
