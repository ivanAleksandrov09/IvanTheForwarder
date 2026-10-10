// The product UI is English; draft content may still use the client's language.
export type UiLang = "en";

const STRINGS = {
  clients: "Clients & risk",
  events: "Events",
  queue: "Ready to send",
  scan: "Scan for events",
  syncInbox: "Sync inbox",
  reset: "Reset demo",
  approve: "Approve & send",
  reject: "Reject",
  save: "Save",
  draftReminder: "Reminder",
  empty: "Nothing waiting for approval.",
  why: "Why",
  loading: "Loading…",
  retry: "Retry",
  confirmSend: "Confirm sending this message.",
  rejectReason: "Rejection reason (optional)",
  history: "History",
} as const;

export type UiKey = keyof typeof STRINGS;
export const t = (key: UiKey, _lang: UiLang) => STRINGS[key];
