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
export type Email = S["Email"];
export type Invoice = S["Invoice"];
export type Incident = S["Incident"];
export type GpsPing = S["GpsPing"];
export type Truck = S["Truck"];
export type MailboxStatus = S["MailboxStatus"];
export type EmailExtraction = S["EmailExtraction"];
export type EmailInsight = S["EmailInsight"];
export type LoadOffer = S["LoadOffer"];
