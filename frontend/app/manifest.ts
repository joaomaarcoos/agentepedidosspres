import type { MetadataRoute } from "next";

const SUCOS_SPRES_LOGO_URL =
  "https://tsnvhhrifxcnuszzaxfk.supabase.co/storage/v1/object/public/app-assets/brand/sucos-spres-logo.png";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "IA Sales Spres",
    short_name: "IA Sales Spres",
    description: "Sistema interno de pedidos, clientes e recorrencia da SucosSpres.",
    start_url: "/pedidos",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0a0b10",
    theme_color: "#0a0b10",
    categories: ["business", "productivity"],
    icons: [
      {
        src: SUCOS_SPRES_LOGO_URL,
        sizes: "1024x1024",
        type: "image/png",
        purpose: "any",
      },
      {
        src: SUCOS_SPRES_LOGO_URL,
        sizes: "1024x1024",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
