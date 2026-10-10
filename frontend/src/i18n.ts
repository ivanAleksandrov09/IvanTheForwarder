// UI strings. TODO(owner C): move every visible string here; add ru/tr/ro if time allows.
export type UiLang = "bg" | "en";

const STRINGS = {
  clients: { bg: "Клиенти и риск", en: "Clients & risk" },
  events: { bg: "Събития", en: "Events" },
  queue: { bg: "Готови за изпращане", en: "Ready to send" },
  scan: { bg: "Сканирай за събития", en: "Scan for events" },
  syncInbox: { bg: "Синхронизирай пощата", en: "Sync inbox" },
  reset: { bg: "Нулирай демото", en: "Reset demo" },
  approve: { bg: "Одобри и изпрати", en: "Approve & send" },
  reject: { bg: "Откажи", en: "Reject" },
  save: { bg: "Запази", en: "Save" },
  draftReminder: { bg: "Напомняне", en: "Reminder" },
  empty: { bg: "Няма чакащи чернови.", en: "Nothing waiting for approval." },
  why: { bg: "Защо", en: "Why" },
} as const;

export type UiKey = keyof typeof STRINGS;
export const t = (key: UiKey, lang: UiLang) => STRINGS[key][lang];
