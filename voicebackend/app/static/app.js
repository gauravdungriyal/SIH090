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
  processing: { asr_provider: null, translation_provider: "Gemini", translation_pending: false },
  created_at: "2026-09-24T10:30:00Z",
  updated_at: "2026-09-24T10:30:00Z",
};

const sampleTranscription = {
  request_id: "97eec61b-1f3a-40c5-9ec7-9fcb619d5001",
  source_language: "hi",
  transcript: "यह हाथ से बना जूट का बैग ₹500 में है।",
  audio_format: "wav",
  sampling_rate_hz: 16000,
  asr_provider: "Gemini",
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
  ["status", "string", "needs_clarification, translation_pending or draft_ready; this service does not publish products."],
  ["intent", "string", "Deterministic classification of the product input."],
  ["source_language", "string", "Input language code."],
  ["original_transcript", "string", "Original typed text or Gemini transcript, retained for review."],
  ["english_translation", "string | null", "Gemini English translation, or the original English input."],
  ["hindi_translation", "string | null", "Gemini Hindi translation, or the original Hindi input."],
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
  ["catalogue.description_translations", "object", "Gemini translations requested for other supported languages."],
  ["missing_fields", "string[]", "Required fields still missing from this draft."],
  ["clarification_questions", "object[]", "English and Hindi questions for the missing fields."],
  ["warnings", "string[]", "Nonfatal extraction or guided-answer warnings."],
  ["processing", "object", "Language-processing providers used for this draft."],
  ["processing.translation_pending", "boolean", "True when a temporary Gemini failure left a requested translation unfinished."],
  ["created_at / updated_at", "datetime", "Draft creation and last update timestamps."],
];

const endpoints = [
  {
    id: "health", group: "1. Service & discovery", label: "Health check", method: "GET", path: "/health", kind: "none",
    description: "Checks that the local API process is responding. This does not call Gemini.",
    docs: "Use this before a demo or integration test to confirm the backend is running.",
    request: [["—", "none", "No path parameters, query parameters or request body are required."]],
    response: [["status", "string", "ok when the API process is running."]],
    sample: { status: "ok" },
  },
  {
    id: "languages", group: "1. Service & discovery", label: "Supported languages", method: "GET", path: "/api/v1/languages", kind: "none",
    description: "Lists language codes accepted by this service and notes the Gemini transcription fallback for Tamil and Urdu.",
    docs: "Show these codes in the source-language selector. Tamil and Urdu use the configurable general audio model; verify accuracy before publishing.",
    request: [["—", "none", "No request body or parameters are required."]],
    response: [["languages", "object[]", "Candidate source language codes and display names."], ["note", "string", "Explains the Gemini transcription fallback for Tamil and Urdu."]],
    sample: { languages: [{ code: "en", name: "English" }, { code: "hi", name: "Hindi" }, { code: "ta", name: "Tamil" }], note: "Gemini's dedicated transcription model supports most listed languages. Tamil and Urdu use the configured audio fallback model; its accuracy may vary." },
  },
  {
    id: "transcribe", group: "2. Voice to text", label: "Transcribe audio", method: "POST", path: "/api/v1/transcriptions/from-audio", kind: "audio",
    description: "Record with your microphone or upload audio, then use Gemini to return only the transcript. No catalogue is created.",
    docs: "Record in the browser or upload WAV, FLAC, MP3 or M4A audio at 8–48 kHz. Default limits are 10 MB and 60 seconds. Set GEMINI_API_KEY on the server. Uploaded audio is deleted from Google's Files API after processing.",
    request: [["audio", "file · required", "A WAV, FLAC, MP3 or M4A recording. Browser recordings are converted to 16 kHz mono WAV."], ...requestFields.language],
    response: [["request_id", "UUID", "Unique call identifier, also sent in X-Request-ID."], ["source_language", "string", "Language selected for Gemini transcription."], ["transcript", "string", "Recognized speech in the source language; no translation or extraction."], ["audio_format", "string", "Validated input format."], ["sampling_rate_hz", "integer", "Validated audio sampling rate."], ["asr_provider", "string", "Gemini."],],
    sample: sampleTranscription,
  },
  {
    id: "from-text", group: "3. Create a catalogue", label: "Create from text", method: "POST", path: "/api/v1/catalogues/from-text", kind: "json",
    description: "Turns a typed transcript into a structured draft. Gemini translates it into Hindi and English before deterministic extraction.",
    docs: "Send a product-related transcript. Off-topic questions are rejected without an answer. If Gemini translation is temporarily unavailable, the original text can still produce an editable draft; missing translations stay null and can be retried.",
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
    id: "from-audio", group: "3. Create a catalogue", label: "Create from audio", method: "POST", path: "/api/v1/catalogues/from-audio", kind: "audio",
    description: "Uploads a recording, validates it, transcribes it with Gemini, and creates an editable catalogue draft.",
    docs: "Upload WAV, FLAC, MP3 or M4A audio at 8–48 kHz. Default limits are 10 MB and 60 seconds. Uploaded audio is deleted from Google's Files API after processing. A temporary translation outage leaves an editable draft with translation_pending=true.",
    request: [
      ["audio", "file · required", "Artisan recording in WAV, FLAC, MP3 or M4A format."],
      ...requestFields.language,
      ["output_languages", "comma-separated string", "Requested languages, for example hi,en."],
      ...requestFields.ids,
      ["X-Idempotency-Key", "header · optional", "Safely retry the same upload without creating another draft."],
    ],
    response: draftResponseFields,
    sample: { ...sampleDraft, processing: { asr_provider: "Gemini", translation_provider: "Gemini", translation_pending: false } },
  },
  {
    id: "guided", group: "4. Guided interview", label: "Submit guided answer", method: "POST", path: "/api/v1/catalogues/guided-answer", kind: "guided",
    description: "Adds one typed or spoken answer to a selected field of an existing draft, then updates its missing-field questions.",
    docs: "Provide exactly one of text or audio. A spoken answer is transcribed by Gemini. Use catalogue_id returned by a creation call.",
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
    id: "validate", group: "4. Guided interview", label: "Validate catalogue", method: "POST", path: "/api/v1/catalogues/validate", kind: "json",
    description: "Checks a catalogue object without saving it or calling Gemini. Useful before an artisan confirms edits.",
    docs: "This endpoint reports missing required fields and invalid values. It does not update an existing draft.",
    request: [["source_language", "string · required", "Language code for the draft."], ["catalogue", "object · required", "Full catalogue field object to validate. Unknown fields are rejected."]],
    response: [["valid", "boolean", "True only when required values are present and all rules pass."], ["missing_fields", "string[]", "Required or conditionally required values still absent."], ["errors", "string[]", "Invalid prices, quantities, dimensions, units or languages."], ["clarification_questions", "object[]", "English and Hindi prompts for missing fields."]],
    example: { source_language: "hi", catalogue: sampleCatalogue },
    sample: { valid: false, missing_fields: ["stock_quantity"], errors: [], clarification_questions: [{ field: "stock_quantity", question_en: "How many units are available?", question_hi: "कितनी इकाइयाँ उपलब्ध हैं?" }] },
  },
  {
    id: "retry-translations", group: "5. Manage drafts", label: "Retry translations", method: "POST", path: "/api/v1/catalogues/{catalogue_id}/retry-translations", kind: "catalogue-id",
    description: "Retries missing Gemini translations for an existing draft without changing extracted product facts.",
    docs: "Use when processing.translation_pending is true. The same catalogue ID is kept. If Gemini is still busy, the draft remains available and the pending flag stays true.",
    request: [["catalogue_id", "UUID · path", "ID of a draft with pending translations."]],
    response: draftResponseFields,
    sample: { ...sampleDraft, status: "translation_pending", english_translation: null, warnings: ["Gemini translation is temporarily unavailable. The original transcript is saved; retry translations before publishing."], processing: { asr_provider: null, translation_provider: null, translation_pending: true } },
  },
  {
    id: "get", group: "5. Manage drafts", label: "Get catalogue", method: "GET", path: "/api/v1/catalogues/{catalogue_id}", kind: "catalogue-id",
    description: "Fetches a saved catalogue draft, including the original transcript, extracted fields and clarification questions.",
    docs: "Use the catalogue_id returned by create or guided-answer. The tester fills the latest ID automatically after a successful call.",
    request: [["catalogue_id", "UUID · path", "ID of the draft to retrieve."]],
    response: draftResponseFields,
    sample: sampleDraft,
  },
  {
    id: "update", group: "5. Manage drafts", label: "Edit catalogue", method: "PUT", path: "/api/v1/catalogues/{catalogue_id}", kind: "update",
    description: "Replaces editable catalogue fields for a saved draft and regenerates descriptions and missing-field questions.",
    docs: "Send the full catalogue object, not only changed fields. The tester uses the latest live draft as a starting point when available.",
    request: [["catalogue_id", "UUID · path", "ID of the draft to edit."], ["catalogue", "object · required", "Complete edited catalogue field object. Description fields are regenerated by the server."]],
    response: draftResponseFields,
    example: { catalogue: { ...sampleCatalogue, stock_quantity: 10 } },
    sample: { ...sampleDraft, status: "draft_ready", intent: "PRODUCT_CORRECTION", catalogue: { ...sampleCatalogue, stock_quantity: 10 }, missing_fields: [], clarification_questions: [] },
  },
  {
    id: "list", group: "5. Manage drafts", label: "List catalogues", method: "GET", path: "/api/v1/catalogues", kind: "list",
    description: "Lists saved drafts with pagination and a basic search across transcripts, identifiers and product names.",
    docs: "Use page and page_size for pagination. Search can match product names, transcripts, artisan IDs or session IDs.",
    request: [["page", "integer · query", "Page number, starting at 1."], ["page_size", "integer · query", "Items per page, 1–100."], ["search", "string · query", "Optional text filter, up to 100 characters."]],
    response: [["items", "object[]", "Catalogue draft responses for this page."], ["total", "integer", "Number of matching drafts."], ["page", "integer", "Current page number."], ["page_size", "integer", "Requested page size."]],
    sample: { items: [sampleDraft], total: 1, page: 1, page_size: 20 },
  },
];

const guidedFields = ["product_name", "category", "materials", "craft_type", "colors", "dimensions", "price", "stock_quantity", "location", "is_handmade", "special_features", "care_instructions", "weight", "currency"];
const languageOptions = ["hi", "en", "bn", "gu", "mr", "ta", "te", "kn", "ml", "pa", "or", "as", "ur"];
const state = { selected: "transcribe", view: "interactive", latestId: "", latestCatalogue: null, responses: {}, transcript: "", transcriptLanguage: "", recordedFile: null, recorder: null, stream: null, recordingTimer: null, previewUrl: null, previewAudio: null };
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
    if (type === "file") input.accept = ".wav,.flac,.mp3,.m4a,audio/wav,audio/flac,audio/mpeg,audio/m4a";
  }
  input.id = `field-${name}`;
  input.name = name;
  wrap.append(label, input);
  if (help) wrap.append(create("span", "field-help", help));
  return wrap;
}

function formNote(text) { return create("p", "form-note", text); }

function recorderControls() {
  const panel = create("div", "recorder-panel");
  panel.append(create("p", "recorder-heading", "Microphone recording"));
  const actions = create("div", "recorder-actions");
  for (const [id, label, action] of [
    ["recordButton", "● Record", startRecording],
    ["stopButton", "■ Stop", stopRecording],
    ["playButton", "▶ Play", playAudio],
    ["transcribeButton", "Transcribe", () => sendRequest(endpoints.find((entry) => entry.id === "transcribe"))],
  ]) {
    const button = create("button", "recorder-button", label);
    button.id = id;
    button.type = "button";
    button.addEventListener("click", action);
    actions.append(button);
  }
  panel.append(actions, create("p", "recorder-status", "Choose an audio file or record using your microphone."));
  panel.lastChild.id = "recorderStatus";
  updateRecorderButtons(panel);
  return panel;
}

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
    grid.append(makeInput("audio", "Audio recording *", "file", "", "WAV, FLAC, MP3 or M4A; at most 10 MB and 60 seconds by default.", [], true));
    grid.append(makeInput("source_language", "Source language *", "select", "hi", "The language spoken in the recording.", languageOptions));
    grid.append(recorderControls());
    if (item.id === "from-audio") {
      grid.append(makeInput("output_languages", "Output languages", "text", "hi,en", "Comma-separated language codes."));
      grid.append(makeInput("artisan_id", "Artisan ID", "text", "", "Optional identifier from your app."));
      grid.append(makeInput("session_id", "Session ID", "text", "", "Optional interview session identifier."));
      grid.append(makeInput("idempotency_key", "X-Idempotency-Key", "text", "", "Optional retry key."));
    }
    grid.append(formNote("Record creates a 16 kHz mono WAV in the browser. Transcribe returns text only; Send Request follows the selected endpoint. Live transcription needs GEMINI_API_KEY in voicebackend/.env."));
  } else if (item.kind === "guided") {
    grid.append(makeInput("catalogue_id", "Catalogue ID *", "text", state.latestId, "The latest created draft ID is filled automatically.", [], true));
    grid.append(makeInput("field", "Field to answer *", "select", "stock_quantity", "Choose one catalogue field.", guidedFields));
    grid.append(makeInput("source_language", "Answer language *", "select", "hi", "Language used in this answer.", languageOptions));
    grid.append(makeInput("text", "Typed answer", "textarea", "10 pieces", "Provide text or an audio recording, not both.", [], true));
    grid.append(makeInput("audio", "Spoken answer", "file", "", "Selecting audio clears the typed answer.", [], true));
    grid.append(formNote("Audio answers use Gemini transcription. Typed answers in a different source language use Gemini translation."));
  } else if (item.kind === "list") {
    grid.append(makeInput("page", "Page", "number", "1", "Starts at 1."));
    grid.append(makeInput("page_size", "Page size", "number", "20", "Choose 1 to 100."));
    grid.append(makeInput("search", "Search", "text", "", "Optional product, transcript, artisan or session text.", [], true));
  }
  container.append(grid);
  if (item.kind === "audio") {
    byId("field-audio").addEventListener("change", () => {
      state.recordedFile = null;
      clearPreview();
      setRecorderStatus(byId("field-audio").files.length ? `Selected ${byId("field-audio").files[0].name}. Ready to play or transcribe.` : "Choose an audio file or record using your microphone.");
      updateRecorderButtons();
    });
    updateRecorderButtons();
  }
  if (item.kind === "guided") {
    const file = byId("field-audio");
    const text = byId("field-text");
    file.addEventListener("change", () => { if (file.files.length) text.value = ""; });
    text.addEventListener("input", () => { if (text.value.trim() && file.files.length) file.value = ""; });
  }
}

function setResponse(status, type, elapsed, content, translationPending = false) {
  const pill = byId("responseStatus");
  pill.className = `status-pill ${type}`;
  pill.textContent = status;
  byId("responseTime").textContent = elapsed;
  byId("liveResponse").textContent = content;
  byId("translationNotice").hidden = !translationPending;
}

function setRecorderStatus(message) {
  if (byId("recorderStatus")) byId("recorderStatus").textContent = message;
}

function selectedAudioFile() {
  return state.recordedFile || byId("field-audio")?.files[0] || null;
}

function updateRecorderButtons(scope = document) {
  const hasAudio = Boolean(state.recordedFile || byId("field-audio")?.files[0]);
  const recording = Boolean(state.recorder && state.recorder.state === "recording");
  const record = scope.querySelector("#recordButton");
  const stop = scope.querySelector("#stopButton");
  const play = scope.querySelector("#playButton");
  const transcribe = scope.querySelector("#transcribeButton");
  if (record) { record.disabled = recording; record.classList.toggle("recording", recording); }
  if (stop) stop.disabled = !recording;
  if (play) play.disabled = !hasAudio || recording;
  if (transcribe) transcribe.disabled = !hasAudio || recording;
}

function clearPreview() {
  if (state.previewAudio) { state.previewAudio.pause(); state.previewAudio = null; }
  if (state.previewUrl) { URL.revokeObjectURL(state.previewUrl); state.previewUrl = null; }
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset, value) => { for (let i = 0; i < value.length; i += 1) view.setUint8(offset + i, value.charCodeAt(i)); };
  write(0, "RIFF");
  view.setUint32(4, buffer.byteLength - 8, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i += 1) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, value < 0 ? value * 0x8000 : value * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function recordingToWav(blob) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass || !window.OfflineAudioContext) throw new Error("This browser cannot convert recordings to WAV. Upload a mono WAV file instead.");
  const context = new AudioContextClass();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    if (!decoded.duration) throw new Error("No audio was recorded. Try again.");
    const rate = 16000;
    const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * rate), rate);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return new File([encodeWav(rendered.getChannelData(0), rate)], "recording.wav", { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setRecorderStatus("Microphone recording needs a supported browser on localhost or HTTPS. You can upload audio instead.");
    return;
  }
  const selectedAtStart = state.selected;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    if (state.selected !== selectedAtStart) { stream.getTracks().forEach((track) => track.stop()); return; }
    state.stream = stream;
    const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      if (state.stream === stream) state.stream = null;
      clearTimeout(state.recordingTimer);
      state.recordingTimer = null;
      if (state.recorder === recorder) state.recorder = null;
      if (state.selected !== selectedAtStart) return;
      setRecorderStatus("Preparing 16 kHz mono WAV…");
      try {
        if (!chunks.length) throw new Error("No audio was recorded. Try again.");
        state.recordedFile = await recordingToWav(new Blob(chunks, { type: recorder.mimeType }));
        if (state.selected !== selectedAtStart) return;
        clearPreview();
        byId("field-audio").value = "";
        setRecorderStatus(`Recording ready (${(state.recordedFile.size / 1024).toFixed(0)} KB, 16 kHz mono WAV). Play it or transcribe it.`);
      } catch (error) {
        state.recordedFile = null;
        setRecorderStatus(`Recording could not be prepared: ${error.message}`);
      }
      updateRecorderButtons();
    };
    state.recordedFile = null;
    clearPreview();
    byId("field-audio").value = "";
    recorder.start(250);
    state.recorder = recorder;
    state.recordingTimer = setTimeout(stopRecording, 59000);
    setRecorderStatus("Recording… Speak now, then click Stop. Recording stops automatically after 59 seconds.");
    updateRecorderButtons();
  } catch (error) {
    if (state.stream) { state.stream.getTracks().forEach((track) => track.stop()); state.stream = null; }
    setRecorderStatus(`Microphone unavailable: ${error.message}. You can upload an audio file instead.`);
    updateRecorderButtons();
  }
}

function stopRecording() {
  if (state.recorder?.state === "recording") {
    state.recorder.stop();
    setRecorderStatus("Finishing recording…");
    updateRecorderButtons();
  }
}

async function playAudio() {
  const file = selectedAudioFile();
  if (!file) { setRecorderStatus("Choose or record audio first."); return; }
  clearPreview();
  state.previewUrl = URL.createObjectURL(file);
  state.previewAudio = new Audio(state.previewUrl);
  state.previewAudio.addEventListener("ended", () => setRecorderStatus("Playback finished. Ready to transcribe."));
  try { await state.previewAudio.play(); setRecorderStatus(`Playing ${file.name}…`); }
  catch (error) { setRecorderStatus(`Playback failed: ${error.message}`); }
}

function showTranscript(transcript, sourceLanguage) {
  state.transcript = transcript;
  state.transcriptLanguage = sourceLanguage;
  byId("transcriptText").textContent = transcript;
  byId("transcriptLanguage").textContent = `Source language: ${sourceLanguage}`;
  byId("transcriptPanel").hidden = false;
}

function selectEndpoint(id) {
  if (state.recorder?.state === "recording") state.recorder.stop();
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
  if (item.kind === "audio" && state.recordedFile) setRecorderStatus(`Recording ready: ${state.recordedFile.name}. Play it or transcribe it.`);
  byId("transcriptPanel").hidden = !state.transcript;
  renderNavigation();
  if (state.responses[id]) {
    const previous = state.responses[id];
    setResponse(previous.status, previous.type, previous.elapsed, previous.content, previous.translationPending);
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
      const file = selectedAudioFile();
      if (!file) throw new Error("Choose an audio recording before sending.");
      form.append("audio", file);
      form.append("source_language", fieldValue("source_language"));
      if (item.id === "from-audio") {
        form.append("output_languages", fieldValue("output_languages") || "hi,en");
        for (const name of ["artisan_id", "session_id"]) if (fieldValue(name)) form.append(name, fieldValue(name));
        if (fieldValue("idempotency_key")) options.headers["X-Idempotency-Key"] = fieldValue("idempotency_key");
      }
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

async function sendRequest(overrideItem = null) {
  const item = overrideItem || endpoint();
  let request;
  try { request = buildRequest(item); }
  catch (error) { setResponse("Input error", "error", "0 ms", error.message); return; }
  const button = byId("sendButton");
  button.disabled = true;
  if (byId("transcribeButton")) byId("transcribeButton").disabled = true;
  byId("sendLabel").textContent = "Sending...";
  byId("responsePath").textContent = request.url;
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
    const translationPending = Boolean(body?.processing?.translation_pending);
    setResponse(status, type, elapsed, content, translationPending);
    state.responses[item.id] = { status, type, elapsed, content, translationPending };
    if (response.ok && body && typeof body === "object") {
      if (typeof body.transcript === "string") showTranscript(body.transcript, body.source_language);
      else if (typeof body.original_transcript === "string") showTranscript(body.original_transcript, body.source_language);
    }
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
    updateRecorderButtons();
    byId("sendLabel").textContent = "Send Request";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  byId("endpointSearch").addEventListener("input", renderNavigation);
  byId("sendButton").addEventListener("click", () => sendRequest());
  byId("retryTranslationsButton").addEventListener("click", () => { selectEndpoint("retry-translations"); sendRequest(); });
  byId("useTranscriptButton").addEventListener("click", () => {
    if (!state.transcript) return;
    selectEndpoint("from-text");
    const payload = JSON.parse(byId("payloadJson").value);
    payload.text = state.transcript;
    payload.source_language = state.transcriptLanguage;
    byId("payloadJson").value = JSON.stringify(payload, null, 2);
    byId("payloadJson").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
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
