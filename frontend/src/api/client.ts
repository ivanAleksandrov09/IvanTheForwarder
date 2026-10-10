// Typed API client. Paths, params and bodies are checked against the GENERATED schema.ts.
// Never hand-write API types: change backend/app/schemas, then `npm run gen:types`.
import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

/** Throws on HTTP errors so callers can use plain try/catch. */
export async function unwrap<T>(p: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await p;
  if (error !== undefined) {
    const detail = (error as { detail?: unknown })?.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(error));
  }
  return data as T;
}
