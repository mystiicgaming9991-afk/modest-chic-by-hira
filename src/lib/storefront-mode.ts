/** The static build and normal local dev use published files; API mode remains available. */
export function isStaticStorefront(): boolean {
  return process.env.NEXT_PUBLIC_STOREFRONT_MODE === "static";
}
