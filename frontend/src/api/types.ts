// Friendly aliases for generated types. Add aliases here; never redefine shapes.
import type { components } from "./schema";

type S = components["schemas"];
export type Client = S["Client"];
export type RiskProfile = S["RiskProfile"];
export type RiskFactor = S["RiskFactor"];
export type DomainEvent = S["DomainEvent"];
export type DraftMessage = S["DraftMessage"];
export type UpdateDraftRequest = S["UpdateDraftRequest"];
export type HealthResponse = S["HealthResponse"];
export type Money = S["Money"];
export type Language = S["Language"];
