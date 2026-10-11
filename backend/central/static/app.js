// Search page for outsiders. Company-written text (names, notes) is only ever inserted with textContent, never as HTML.
const TRAILERS = ["tent", "mega", "reefer", "flatbed", "tanker", "box"];
const CARGO = ["general", "palletized", "refrigerated", "pharma", "adr_dangerous", "oversized", "bulk", "food", "textile", "steel", "grain", "furniture", "automotive"];
const LANGUAGES = ["bg", "en", "ru", "tr", "ro"];
const PAGE = 20;
const $ = (id) => document.getElementById(id);
let offset = 0;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function checkboxes(container, name, options) {
  for (const option of options) {
    const label = element("label", "inline");
    const input = element("input");
    input.type = "checkbox";
    input.name = name;
    input.value = option;
    label.append(input, " " + option);
    container.append(label);
  }
}

const checked = (name) => [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value);
const list = (id, upper) => $(id).value.split(",").map((s) => (upper ? s.trim().toUpperCase() : s.trim())).filter(Boolean);

function query() {
  const p = new URLSearchParams();
  for (const c of list("countries", true)) p.append("country", c);
  for (const l of list("lanes", true)) p.append("lane", l);
  for (const t of checked("trailer")) p.append("trailer", t);
  for (const c of checked("cargo")) p.append("cargo", c);
  for (const l of checked("language")) p.append("language", l);
  if ($("min_load").value) p.set("min_load_kg", $("min_load").value);
  if ($("adr").checked) p.set("adr", "true");
  if ($("region").value.trim()) p.set("region", $("region").value.trim());
  if ($("q").value.trim()) p.set("q", $("q").value.trim());
  p.set("limit", String(PAGE));
  p.set("offset", String(offset));
  return p;
}

function chips(values) {
  const row = element("div", "chips");
  for (const v of values) row.append(element("span", "chip", v));
  return row;
}

function card(match) {
  const c = match.profile;
  const node = element("article", "card");
  node.append(element("h3", "", c.name + (c.name_latin && c.name_latin !== c.name ? ` / ${c.name_latin}` : "")));
  node.append(element("p", "muted", [c.home_region, `${c.fleet.trucks} trucks`, `up to ${c.max_load_kg.toLocaleString()} kg`, c.adr ? "ADR" : ""].filter(Boolean).join(" · ")));
  if (c.countries_served.length) node.append(element("p", "", "Countries: " + c.countries_served.join(", ")));
  if (c.lanes.length) node.append(element("p", "", "Main lanes: " + c.lanes.map((l) => `${l.from_country} → ${l.to_country} (${l.shipments})`).join(", ")));
  if (c.trailer_types.length) node.append(chips(c.trailer_types));
  if (c.cargo_types.length) node.append(chips(c.cargo_types));
  if (c.languages.length) node.append(element("p", "muted", "Languages: " + c.languages.join(", ")));
  if (c.public_notes) node.append(element("p", "", c.public_notes));
  if (c.contact_email || c.contact_phone) {
    const contact = element("p", "contact");
    if (c.contact_email) {
      const link = element("a", "", c.contact_email);
      link.href = "mailto:" + encodeURIComponent(c.contact_email);
      contact.append(link, " ");
    }
    if (c.contact_phone) contact.append(c.contact_phone);
    node.append(contact);
  }
  return node;
}

async function run(append) {
  if (!append) {
    offset = 0;
    $("results").replaceChildren();
  }
  $("status").textContent = "Searching…";
  try {
    const response = await fetch("/api/v1/search?" + query());
    if (!response.ok) throw new Error(response.status === 422 ? "Please check your filters (country codes are 2 letters, lanes look like BG-DE)." : `Search failed (${response.status}).`);
    const data = await response.json();
    for (const match of data.items) $("results").append(card(match));
    offset += data.items.length;
    $("more").hidden = offset >= data.total;
    $("status").textContent = data.total === 0 ? "No companies match these filters." : `${data.total} ${data.total === 1 ? "company matches" : "companies match"}.`;
  } catch (err) {
    $("status").textContent = err.message;
  }
}

checkboxes($("trailers"), "trailer", TRAILERS);
checkboxes($("cargo"), "cargo", CARGO);
checkboxes($("languages"), "language", LANGUAGES);
$("filters").addEventListener("submit", (e) => { e.preventDefault(); run(false); });
$("filters").addEventListener("reset", () => setTimeout(() => run(false)));
$("more").addEventListener("click", () => run(true));
run(false);
