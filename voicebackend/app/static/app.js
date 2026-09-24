"use strict";

const sampleCatalogue = {
  product_name: "Jute Bag", category: "Bag", materials: ["Jute"], craft_type: null,
  colors: [], price: 500, currency: "INR", stock_quantity: null,
  dimensions: { length: null, width: null, height: null, unit: null },
  weight: null, weight_unit: null, location: null, is_handmade: true,
  special_features: [], care_instructions: null,
  description_en: "This is a handmade Jute Bag. Made using Jute. Priced at ₹500.",
  description_hi: "यह हस्तनिर्मित जूट बैग है। जूट से बनाया गया है। इसकी कीमत ₹500 है।",
  description_translations: {},
};

const sampleDraft = {
  request_id: "97eec61b-1f3a-40c5-9ec7-9fcb619d5001",
  catalogue_id: "ac3b59d5-cf94-4721-8215-f41511426812",
  status: "needs_clarification",
  intent: "PRODUCT_DESCRIPTION",
  source_language: "hi",
  original_transcript: "यह हाथ से बना जूट का बैग ₹500 में है।",
  english_translation: "This is a handmade jute bag priced at 500 rupees.",
  hindi_translation: "यह हाथ से बना जूट का बैग ₹500 में है।",
  catalogue: sampleCatalogue,
  missing_fields: ["stock_quantity"],
  clarification_questions: [{
    field: "stock_quantity", question_en: "How many units are available?",
    question_hi: "कितनी इकाइयाँ उपलब्ध हैं?",
  }],
  warnings: [],
  processing: { asr_provider: null, translation_provider: "Bhashini" },
  created_at: "2026-09-24T10:30:00Z",
  updated_at: "2026-09-24T10:30:00Z",
};

const requestFields = {
  language: [
    ["source_language", "string · required", "ISO language code of the spoken or typed input, such as hi or en."],
  ],
  ids: [
    ["artisan_id", "string · optional", "Your application's identifier for the artisan; saved with the draft."],
    ["session_id", "string · optional", "Groups answers from one catalogue interview session."],
  ],
};

const draftResponseFields = [
  ["request_id", "UUID", "Unique identifier for this API call; also sent in the X-Request-ID header."],
  ["catalogue_id", "UUID", "Identifier to use for guided answers, reads and edits."],
  ["status", "string", "needs_clarification or draft_ready; this service does not publish products."],
  ["intent", "string", "Deterministic classification of the product input."],
  ["source_language", "string", "Input language code."],
  ["original_transcript", "string", "Original typed text or Bhashini ASR transcript, retained for review."],
  ["english_translation", "string | null", "Bhashini English translation, or the original English input."],
  ["hindi_translation", "string | null", "Bhashini Hindi translation, or the original Hindi input."],
  ["catalogue.product_name", "string | null", "Product name inferred from observed details or supplied by the artisan."],
  ["catalogue.category", "string | null", "Mapped product type, such as Bag or Saree."],
  ["catalogue.materials", "string[]", "Observed materials; empty when none are recognized."],
  ["catalogue.craft_type", "string | null", "Recognized craft or technique."],
  ["catalogue.colors", "string[]", "Recognized colours."],
  ["catalogue.price", "number | null", "Positive selling price, when supplied."],
  ["catalogue.currency", "string | null", "INR only for an explicit rupee cue or configured default."],
  ["catalogue.stock_quantity", "integer | null", "Available units. Zero is valid."],
  ["catalogue.dimensions", "object", "Length, width, height and normalized unit; missing measurements stay null."],
  ["catalogue.weight", "number | null", "Positive weight, when supplied."],
  ["catalogue.weight_unit", "string | null", "Normalized g or kg unit."],
  ["catalogue.location", "string | null", "Place of making, when supplied."],
  ["catalogue.is_handmade", "boolean | null", "Whether the artisan explicitly described the product as handmade."],
  ["catalogue.special_features", "string[]", "Features explicitly supplied by the artisan."],
  ["catalogue.care_instructions", "string | null", "Buyer care instructions, when supplied."],
  ["catalogue.description_en", "string | null", "Controlled English template using known facts only."],
  ["catalogue.description_hi", "string | null", "Controlled Hindi template using known facts only."],
  ["catalogue.description_translations", "object", "Bhashini translations requested for other supported languages."],
  ["missing_fields", "string[]", "Required fields still missing from this draft."],
  ["clarification_questions", "object[]", "English and Hindi questions for the missing fields."],
  ["warnings", "string[]", "Nonfatal extraction or guided-answer warnings."],
  ["processing", "object", "Language-processing providers used for this draft."],
  ["created_at / updated_at", "datetime", "Draft creation and last update timestamps."],
];

const endpoints = [
  {
    id: "health", group: "1. Service & discovery", label: "Health check", method: "GET", path: "/health", kind: "none",
    description: "Checks that the local API process is responding. This does not call Bhashini.",
    docs: "Use this before a demo or integration test to confirm the backend is running.",
    request: [["—", "none", "No path parameters, query parameters or request body are required."]],
    response: [["status", "string", "ok when the API process is running."]],
    sample: { status: "ok" },
  },
  {
    id: "languages", group: "1. Service & discovery", label: "Supported languages", method: "GET", path: "/api/v1/languages", kind: "none",
    description: "Lists language codes accepted by this service and notes that actual model support depends on your Bhashini pipeline.",
    docs: "Show these codes in the source-language selector. A selected Bhashini model may support a smaller set.",
    request: [["—", "none", "No request body or parameters are required."]],
    response: [["languages", "object[]", "Candidate source language codes and display names."], ["note", "string", "Explains the Bhashini model-availability limitation."]],
    sample: { languages: [{ code: "en", name: "English" }, { code: "hi", name: "Hindi" }, { code: "ta", name: "Tamil" }], note: "Actual ASR and translation support depends on the configured Bhashini pipeline." },
  },
  {
    id: "from-text", group: "2. Create a catalogue", label: "Create from text", method: "POST", path: "/api/v1/catalogues/from-text", kind: "json",
    description: "Turns a typed transcript into a structured draft. Bhashini translates it into Hindi and English before deterministic extraction.",
    docs: "Send a product-related transcript. Off-topic questions are rejected without an answer. Translation needs Bhashini credentials.",
    request: [
      ["text", "string · required", "Artisan's product description or transcript; cannot be empty."],
      ...requestFields.language,
      ["output_languages", "string[]", "Desired description languages; Hindi and English are always generated."],
      ...requestFields.ids,
      ["X-Idempotency-Key", "header · optional", "Reuse for safe retries of the same request; different content with the same key returns 409."],
    ],
    response: draftResponseFields,
    example: { text: "यह हाथ से बना जूट का बैग ₹500 में है।", source_language: "hi", output_languages: ["hi", "en"], artisan_id: "artisan-001", session_id: "session-001" },
    sample: sampleDraft,
  },
  {
    id: "from-audio", group: "2. Create a catalogue", label: "Create from audio", method: "POST", path: "/api/v1/catalogues/from-audio", kind: "audio",
    description: "Uploads a recording, validates it, transcribes it with Bhashini ASR, and creates an editable catalogue draft.",
    docs: "Upload mono WAV, FLAC or MP3 audio at 8–48 kHz. Default limits are 10 MB and 60 seconds. Raw audio is not permanently stored.",
    request: [
      ["audio", "file · required", "Artisan recording in WAV, FLAC or MP3 format."],
      ...requestFields.language,
      ["output_languages", "comma-separated string", "Requested languages, for example hi,en."],
      ...requestFields.ids,
      ["X-Idempotency-Key", "header · optional", "Safely retry the same upload without creating another draft."],
    ],
    response: draftResponseFields,
    sample: { ...sampleDraft, processing: { asr_provider: "Bhashini", translation_provider: "Bhashini" } },
  },
  {
    id: "guided", group: "3. Guided interview", label: "Submit guided answer", method: "POST", path: "/api/v1/catalogues/guided-answer", kind: "guided",
    description: "Adds one typed or spoken answer to a selected field of an existing draft, then updates its missing-field questions.",
    docs: "Provide exactly one of text or audio. A spoken answer is transcribed by Bhashini. Use catalogue_id returned by a creation call.",
    request: [
      ["catalogue_id", "UUID · required", "Existing draft to update."],
      ["field", "string · required", "Catalogue field being answered, such as stock_quantity or materials."],
      ...requestFields.language,
      ["text", "string · optional", "Typed answer. Use this or audio, not both."],
      ["audio", "file · optional", "Spoken answer in a supported audio format. Use this or text, not both."],
    ],
    response: draftResponseFields,
    sample: { ...sampleDraft, status: "draft_ready", intent: "PRODUCT_CORRECTION", catalogue: { ...sampleCatalogue, stock_quantity: 10 }, missing_fields: [], clarification_questions: [] },
  },
  {
    id: "validate", group: "3. Guided interview", label: "Validate catalogue", method: "POST", path: "/api/v1/catalogues/validate", kind: "json",
    description: "Checks a catalogue object without saving it or calling Bhashini. Useful before an artisan confirms edits.",
    docs: "This endpoint reports missing required fields and invalid values. It does not update an existing draft.",
    request: [["source_language", "string · required", "Language code for the draft."], ["catalogue", "object · required", "Full catalogue field object to validate. Unknown fields are rejected."]],
    response: [["valid", "boolean", "True only when required values are present and all rules pass."], ["missing_fields", "string[]", "Required or conditionally required values still absent."], ["errors", "string[]", "Invalid prices, quantities, dimensions, units or languages."], ["clarification_questions", "object[]", "English and Hindi prompts for missing fields."]],
    example: { source_language: "hi", catalogue: sampleCatalogue },
    sample: { valid: false, missing_fields: ["stock_quantity"], errors: [], clarification_questions: [{ field: "stock_quantity", question_en: "How many units are available?", question_hi: "कितनी इकाइयाँ उपलब्ध हैं?" }] },
  },
  {
    id: "get", group: "4. Manage drafts", label: "Get catalogue", method: "GET", path: "/api/v1/catalogues/{catalogue_id}", kind: "catalogue-id",
    description: "Fetches a saved catalogue draft, including the original transcript, extracted fields and clarification questions.",
    docs: "Use the catalogue_id returned by create or guided-answer. The tester fills the latest ID automatically after a successful call.",
    request: [["catalogue_id", "UUID · path", "ID of the draft to retrieve."]],
    response: draftResponseFields,
    sample: sampleDraft,
  },
  {
    id: "update", group: "4. Manage drafts", label: "Edit catalogue", method: "PUT", path: "/api/v1/catalogues/{catalogue_id}", kind: "update",
    description: "Replaces editable catalogue fields for a saved draft and regenerates descriptions and missing-field questions.",
    docs: "Send the full catalogue object, not only changed fields. The tester uses the latest live draft as a starting point when available.",
    request: [["catalogue_id", "UUID · path", "ID of the draft to edit."], ["catalogue", "object · required", "Complete edited catalogue field object. Description fields are regenerated by the server."]],
    response: draftResponseFields,
    example: { catalogue: { ...sampleCatalogue, stock_quantity: 10 } },
    sample: { ...sampleDraft, status: "draft_ready", intent: "PRODUCT_CORRECTION", catalogue: { ...sampleCatalogue, stock_quantity: 10 }, missing_fields: [], clarification_questions: [] },
  },
  {
    id: "list", group: "4. Manage drafts", label: "List catalogues", method: "GET", path: "/api/v1/catalogues", kind: "list",
    description: "Lists saved drafts with pagination and a basic search across transcripts, identifiers and product names.",
    docs: "Use page and page_size for pagination. Search can match product names, transcripts, artisan IDs or session IDs.",
    request: [["page", "integer · query", "Page number, starting at 1."], ["page_size", "integer · query", "Items per page, 1–100."], ["search", "string · query", "Optional text filter, up to 100 characters."]],
    response: [["items", "object[]", "Catalogue draft responses for this page."], ["total", "integer", "Number of matching drafts."], ["page", "integer", "Current page number."], ["page_size", "integer", "Requested page size."]],
    sample: { items: [sampleDraft], total: 1, page: 1, page_size: 20 },
  },
];

const guidedFields = ["product_name", "category", "materials", "craft_type", "colors", "dimensions", "price", "stock_quantity", "location", "is_handmade", "special_features", "care_instructions", "weight", "currency"];
const languageOptions = ["hi", "en", "bn", "gu", "mr", "ta", "te", "kn", "ml", "pa", "or", "as", "ur"];
const state = { selected: "from-text", view: "interactive", latestId: "", latestCatalogue: null, responses: {} };
const byId = (id) => document.getElementById(id);

function create(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function methodClass(method) { return `method-${method.toLowerCase()}`; }
function endpoint() { return endpoints.find((item) => item.id === state.selected); }

function renderNavigation() {
  const query = byId("endpointSearch").value.trim().toLowerCase();
  const container = byId("endpointNav");
  container.replaceChildren();
  const groups = [...new Set(endpoints.map((item) => item.group))];
  let count = 0;
  for (const groupName of groups) {
    const visible = endpoints.filter((item) => item.group === groupName && `${item.label} ${item.path} ${item.description}`.toLowerCase().includes(query));
    if (!visible.length) continue;
    const group = create("div", "nav-group");
    group.append(create("div", "nav-group-title", groupName));
    for (const item of visible) {
      const button = create("button", `endpoint-nav-button${item.id === state.selected ? " active" : ""}`);
      button.type = "button";
      button.setAttribute("aria-current", item.id === state.selected ? "page" : "false");
      const badge = create("span", `method-mini ${methodClass(item.method)}`, item.method);
      button.append(badge, create("span", "nav-label", item.label));
      button.addEventListener("click", () => selectEndpoint(item.id));
      group.append(button);
      count += 1;
    }
    container.append(group);
  }
  byId("endpointCount").textContent = String(count);
  if (!count) container.append(create("p", "field-help", "No matching endpoints."));
}

function renderFieldTable(targetId, rows) {
  const target = byId(targetId);
  target.replaceChildren();
  for (const [name, type, meaning] of rows) {
    const row = create("tr");
    const nameCell = create("td");
    nameCell.append(create("code", "", name));
    row.append(nameCell, create("td", "", type), create("td", "", meaning));
    target.append(row);
  }
}

function makeInput(name, labelText, type, value = "", help = "", options = [], full = false) {
  const wrap = create("div", `form-field${full ? " full" : ""}`);
  const label = create("label", "", labelText);
  label.htmlFor = `field-${name}`;
  let input;
  if (type === "select") {
    input = create("select", "form-control");
    for (const option of options) {
      const element = create("option", "", option);
      element.value = option;
      input.append(element);
    }
    input.value = value;
  } else if (type === "textarea") {
    input = create("textarea", "form-control");
    input.value = value;
  } else {
    input = create("input", "form-control");
    input.type = type;
    if (type !== "file") input.value = value;
    if (type === "file") input.accept = ".wav,.flac,.mp3,audio/wav,audio/flac,audio/mpeg";
  }
  input.id = `field-${name}`;
  input.name = name;
  wrap.append(label, input);
  if (help) wrap.append(create("span", "field-help", help));
  return wrap;
}

function formNote(text) { return create("p", "form-note", text); }

function renderEditor(item) {
  const container = byId("requestEditor");
  container.replaceChildren();
  const isJson = item.kind === "json" || item.kind === "update";
  byId("requestHeading").textContent = isJson ? "Request payload (JSON)" : item.kind === "none" ? "Request" : "Request fields";
  byId("requestHint").textContent = isJson ? "Edit the JSON before sending" : item.kind === "none" ? "No input needed" : "Edit fields before sending";

  if (item.kind === "none") {
    const box = create("div", "form-grid");
    box.append(formNote("No request body or parameters are needed. Click Send Request to call this endpoint."));
    container.append(box);
    return;
  }
  if (item.kind === "catalogue-id" || item.kind === "update") {
    const box = create("div", "form-grid");
    box.append(makeInput("catalogue_id", "Catalogue ID", "text", state.latestId, "Paste a saved draft UUID, or create a draft first.", [], true));
    container.append(box);
  }
  if (isJson) {
    const editor = create("textarea", "json-editor");
    editor.id = "payloadJson";
    editor.setAttribute("aria-label", "JSON request payload");
    const payload = item.kind === "update" && state.latestCatalogue ? { catalogue: state.latestCatalogue } : item.example;
    editor.value = JSON.stringify(payload, null, 2);
    container.append(editor);
    if (item.id === "from-text") {
      const box = create("div", "form-grid");
      box.style.marginTop = "12px";
      box.append(makeInput("idempotency_key", "X-Idempotency-Key (optional)", "text", "", "Use the same key only when retrying identical input.", [], true));
      container.append(box);
    }
    return;
  }
  if (item.kind === "catalogue-id") return;
  const grid = create("div", "form-grid");
  if (item.kind === "audio") {
    grid.append(makeInput("audio", "Audio recording *", "file", "", "Mono WAV, FLAC or MP3; at most 10 MB and 60 seconds by default.", [], true));
    grid.append(makeInput("source_language", "Source language *", "select", "hi", "The language spoken in the recording.", languageOptions));
    grid.append(makeInput("output_languages", "Output languages", "text", "hi,en", "Comma-separated language codes."));
    grid.append(makeInput("artisan_id", "Artisan ID", "text", "", "Optional identifier from your app."));
    grid.append(makeInput("session_id", "Session ID", "text", "", "Optional interview session identifier."));
    grid.append(makeInput("idempotency_key", "X-Idempotency-Key", "text", "", "Optional retry key."));
    grid.append(formNote("This endpoint calls Bhashini ASR and translation. Set BHASHINI_* values in voicebackend/.env first."));
  } else if (item.kind === "guided") {
    grid.append(makeInput("catalogue_id", "Catalogue ID *", "text", state.latestId, "The latest created draft ID is filled automatically.", [], true));
    grid.append(makeInput("field", "Field to answer *", "select", "stock_quantity", "Choose one catalogue field.", guidedFields));
    grid.append(makeInput("source_language", "Answer language *", "select", "hi", "Language used in this answer.", languageOptions));
    grid.append(makeInput("text", "Typed answer", "textarea", "10 pieces", "Provide text or an audio recording, not both.", [], true));
    grid.append(makeInput("audio", "Spoken answer", "file", "", "Selecting audio clears the typed answer.", [], true));
    grid.append(formNote("Audio answers use Bhashini ASR. Typed answers in a different source language use Bhashini translation."));
  } else if (item.kind === "list") {
    grid.append(makeInput("page", "Page", "number", "1", "Starts at 1."));
    grid.append(makeInput("page_size", "Page size", "number", "20", "Choose 1 to 100."));
    grid.append(makeInput("search", "Search", "text", "", "Optional product, transcript, artisan or session text.", [], true));
  }
  container.append(grid);
  if (item.kind === "guided") {
    const file = byId("field-audio");
    const text = byId("field-text");
    file.addEventListener("change", () => { if (file.files.length) text.value = ""; });
    text.addEventListener("input", () => { if (text.value.trim() && file.files.length) file.value = ""; });
  }
}

function setResponse(status, type, elapsed, content) {
  const pill = byId("responseStatus");
  pill.className = `status-pill ${type}`;
  pill.textContent = status;
  byId("responseTime").textContent = elapsed;
  byId("liveResponse").textContent = content;
}

function selectEndpoint(id) {
  state.selected = id;
  history.replaceState(null, "", `#${id}`);
  const item = endpoint();
  byId("methodBadge").className = `method-badge ${methodClass(item.method)}`;
  byId("methodBadge").textContent = item.method;
  byId("endpointTitle").textContent = item.label;
  byId("endpointPath").textContent = item.path;
  byId("endpointDescription").textContent = item.description;
  byId("responsePath").textContent = item.path;
  byId("docsEndpointName").textContent = item.label;
  byId("docsSummary").textContent = item.docs;
  byId("sampleOutput").textContent = JSON.stringify(item.sample, null, 2);
  renderFieldTable("requestFields", item.request);
  renderFieldTable("responseFields", item.response);
  renderEditor(item);
  renderNavigation();
  if (state.responses[id]) {
    const previous = state.responses[id];
    setResponse(previous.status, previous.type, previous.elapsed, previous.content);
  } else {
    setResponse("Ready", "ready", "0 ms", "Click “Send Request” to execute this endpoint.");
  }
  setView("interactive");
}

function setView(view) {
  state.view = view;
  const views = { interactive: "interactiveView", "deep-dive": "deepDiveView", "all-endpoints": "allEndpointsView" };
  for (const [key, elementId] of Object.entries(views)) {
    const visible = key === view;
    byId(elementId).hidden = !visible;
    byId(elementId).classList.toggle("active", visible);
  }
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-current", active ? "page" : "false");
  });
}

function renderEndpointGrid() {
  const grid = byId("endpointGrid");
  grid.replaceChildren();
  for (const item of endpoints) {
    const card = create("button", "endpoint-tile");
    card.type = "button";
    const top = create("span", "endpoint-tile-top");
    top.append(create("span", `method-mini ${methodClass(item.method)}`, item.method), create("strong", "", item.label));
    card.append(top, create("code", "", item.path), create("p", "", item.description));
    card.addEventListener("click", () => { selectEndpoint(item.id); window.scrollTo({ top: 0, behavior: "smooth" }); });
    grid.append(card);
  }
}

function fieldValue(name) { return byId(`field-${name}`)?.value.trim() || ""; }

function buildRequest(item) {
  let url = item.path;
  const options = { method: item.method, headers: { Accept: "application/json" } };
  if (item.kind === "json" || item.kind === "update") {
    let payload;
    try { payload = JSON.parse(byId("payloadJson").value); }
    catch { throw new Error("Request payload must be valid JSON."); }
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
    if (item.id === "from-text" && fieldValue("idempotency_key")) options.headers["X-Idempotency-Key"] = fieldValue("idempotency_key");
  }
  if (item.kind === "catalogue-id" || item.kind === "update") {
    const id = fieldValue("catalogue_id");
    if (!id) throw new Error("Enter a catalogue ID first. Create a draft or paste an existing ID.");
    url = url.replace("{catalogue_id}", encodeURIComponent(id));
  }
  if (item.kind === "list") {
    const params = new URLSearchParams();
    params.set("page", fieldValue("page") || "1");
    params.set("page_size", fieldValue("page_size") || "20");
    if (fieldValue("search")) params.set("search", fieldValue("search"));
    url += `?${params.toString()}`;
  }
  if (item.kind === "audio" || item.kind === "guided") {
    const form = new FormData();
    if (item.kind === "audio") {
      const file = byId("field-audio").files[0];
      if (!file) throw new Error("Choose an audio recording before sending.");
      form.append("audio", file);
      form.append("source_language", fieldValue("source_language"));
      form.append("output_languages", fieldValue("output_languages") || "hi,en");
      for (const name of ["artisan_id", "session_id"]) if (fieldValue(name)) form.append(name, fieldValue(name));
      if (fieldValue("idempotency_key")) options.headers["X-Idempotency-Key"] = fieldValue("idempotency_key");
    } else {
      const id = fieldValue("catalogue_id");
      const text = fieldValue("text");
      const file = byId("field-audio").files[0];
      if (!id) throw new Error("Enter a catalogue ID first.");
      if (Boolean(text) === Boolean(file)) throw new Error("Provide exactly one answer: typed text or an audio file.");
      form.append("catalogue_id", id);
      form.append("field", fieldValue("field"));
      form.append("source_language", fieldValue("source_language"));
      if (file) form.append("audio", file); else form.append("text", text);
    }
    options.body = form;
  }
  return { url, options };
}

async function sendRequest() {
  const item = endpoint();
  let request;
  try { request = buildRequest(item); }
  catch (error) { setResponse("Input error", "error", "0 ms", error.message); return; }
  const button = byId("sendButton");
  button.disabled = true;
  byId("sendLabel").textContent = "Sending...";
  setResponse("Sending", "loading", "…", `Calling ${item.method} ${request.url}…`);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  const started = performance.now();
  try {
    const response = await fetch(request.url, { ...request.options, signal: controller.signal });
    const raw = await response.text();
    let body;
    try { body = JSON.parse(raw); } catch { body = raw; }
    const elapsed = `${Math.round(performance.now() - started)} ms`;
    const status = `${response.status} ${response.statusText}`.trim();
    const content = typeof body === "string" ? body : JSON.stringify(body, null, 2);
    const type = response.ok ? "success" : "error";
    setResponse(status, type, elapsed, content);
    state.responses[item.id] = { status, type, elapsed, content };
    if (response.ok && body && typeof body === "object" && body.catalogue_id) {
      state.latestId = body.catalogue_id;
      state.latestCatalogue = body.catalogue || null;
    }
  } catch (error) {
    const elapsed = `${Math.round(performance.now() - started)} ms`;
    const message = error.name === "AbortError" ? "Request timed out after 120 seconds." : `Could not reach the local API: ${error.message}`;
    setResponse("Request failed", "error", elapsed, message);
    state.responses[item.id] = { status: "Request failed", type: "error", elapsed, content: message };
  } finally {
    clearTimeout(timer);
    button.disabled = false;
    byId("sendLabel").textContent = "Send Request";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  byId("endpointSearch").addEventListener("input", renderNavigation);
  byId("sendButton").addEventListener("click", sendRequest);
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => setView(tab.dataset.view)));
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && state.view === "interactive") {
      event.preventDefault();
      sendRequest();
    }
  });
  renderEndpointGrid();
  const initial = location.hash.slice(1);
  selectEndpoint(endpoints.some((item) => item.id === initial) ? initial : state.selected);
});
