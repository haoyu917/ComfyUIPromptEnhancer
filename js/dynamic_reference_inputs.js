import { app } from "../../scripts/app.js";

const REF_PREFIX = "reference_image_";
const CLASS_NAME = "BUFF_AIDirectorPromptEnhancer";
const GENERIC_TITLES = new Set([
  "load image", "loadimage", "加载图像", "加载图片", "image", "图像",
  "preview image", "预览图像"
]);

function refInputs(node) {
  return (node.inputs || [])
    .filter((i) => i && typeof i.name === "string" && i.name.startsWith(REF_PREFIX))
    .sort((a, b) => {
      const ai = parseInt(a.name.slice(REF_PREFIX.length)) || 0;
      const bi = parseInt(b.name.slice(REF_PREFIX.length)) || 0;
      return ai - bi;
    });
}

function ensureOneSpareRefInput(node) {
  if (!node.inputs) return;

  let refs = refInputs(node);
  if (refs.length === 0) {
    node.addInput(`${REF_PREFIX}1`, "IMAGE");
    refs = refInputs(node);
  }

  const last = refs[refs.length - 1];
  if (last && last.link != null) {
    const nextIndex = (parseInt(last.name.slice(REF_PREFIX.length)) || refs.length) + 1;
    node.addInput(`${REF_PREFIX}${nextIndex}`, "IMAGE");
    refs = refInputs(node);
  }

  while (refs.length >= 2) {
    const lastRef = refs[refs.length - 1];
    const prevRef = refs[refs.length - 2];
    const lastEmpty = lastRef.link == null;
    const prevEmpty = prevRef.link == null;
    if (!(lastEmpty && prevEmpty)) break;
    const idx = node.inputs.findIndex((i) => i === lastRef);
    if (idx >= 0) node.removeInput(idx);
    refs = refInputs(node);
  }

  node.setDirtyCanvas?.(true, true);
}

function findWidget(node, name) {
  return node.widgets?.find((widget) => widget?.name === name);
}

function getGraphLink(linkId) {
  if (linkId == null) return null;
  const links = app.graph?.links;
  if (!links) return null;
  if (typeof links.get === "function") return links.get(linkId) || null;
  return links[linkId] || links[String(linkId)] || null;
}

function cleanFilename(value) {
  if (typeof value !== "string" || !value.trim()) return "";
  const base = value.trim().split(/[\\/]/).pop() || value.trim();
  return base.replace(/\.[a-zA-Z0-9]{1,8}$/, "").trim();
}

function sourceNodeForInput(input) {
  const link = getGraphLink(input?.link);
  if (!link) return null;
  const originId = link.origin_id ?? link.originId;
  if (originId == null) return null;
  return app.graph?.getNodeById?.(originId) || null;
}


function asEntityToken(value, index) {
  const text = String(value || "").trim();
  if (!text) return `@参考图${index}`;
  if (text.startsWith("@")) return text;
  return `@${text}`;
}

function sourceReferenceName(input, index) {
  const originNode = sourceNodeForInput(input);
  if (!originNode) return "";

  const title = String(originNode.title || "").trim();
  const normalized = title.toLowerCase();
  if (title && !GENERIC_TITLES.has(normalized)) {
    return asEntityToken(title, index);
  }

  const fileWidget = originNode.widgets?.find((w) =>
    ["image", "filename", "file", "path"].includes(String(w?.name || "").toLowerCase())
  );
  const fromFile = cleanFilename(fileWidget?.value);
  if (fromFile) return asEntityToken(fromFile, index);

  return asEntityToken(`参考图${index}`, index);
}

function parseManifest(text) {
  const map = new Map();
  for (const raw of String(text || "").split(/\r?\n/)) {
    const match = raw.trim().match(/^(\d+)\s*(?:[:=：\-.])\s*(.+)$/);
    if (match) map.set(parseInt(match[1]), match[2].trim());
  }
  return map;
}

function syncReferenceLabels(node, manifestText) {
  const manual = parseManifest(manifestText);
  for (const input of refInputs(node)) {
    const index = parseInt(input.name.slice(REF_PREFIX.length)) || 0;
    if (input.link == null) {
      input.label = `参考图 ${index}`;
      continue;
    }
    const name = manual.get(index) || sourceReferenceName(input, index);
    input.label = name ? `参考图 ${index} · ${name}` : `参考图 ${index}`;
  }
}

function syncAutoReferenceManifest(node) {
  const autoWidget = findWidget(node, "auto_reference_names");
  const manifestWidget = findWidget(node, "reference_manifest");
  if (!manifestWidget) return;

  const autoEnabled = autoWidget ? Boolean(autoWidget.value) : true;
  if (!autoEnabled) {
    syncReferenceLabels(node, manifestWidget.value);
    return;
  }

  const lines = [];
  for (const input of refInputs(node)) {
    if (input.link == null) continue;
    const index = parseInt(input.name.slice(REF_PREFIX.length)) || 0;
    const name = sourceReferenceName(input, index) || `参考图 ${index}`;
    lines.push(`${index}=${name}`);
  }
  const next = lines.join("\n");
  if (String(manifestWidget.value || "") !== next) {
    manifestWidget.value = next;
    manifestWidget.callback?.(next);
  }
  syncReferenceLabels(node, next);
}

function refreshReferences(node) {
  ensureOneSpareRefInput(node);
  syncAutoReferenceManifest(node);
  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "buff_ai.dynamic_reference_inputs",
  async nodeCreated(node) {
    if (node.comfyClass !== CLASS_NAME) return;

    const orig = node.onConnectionsChange?.bind(node);
    node.onConnectionsChange = function (...args) {
      const out = orig?.(...args);
      queueMicrotask(() => refreshReferences(node));
      return out;
    };

    const origConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (...args) {
      const out = origConfigure?.(...args);
      queueMicrotask(() => refreshReferences(node));
      return out;
    };

    const autoWidget = findWidget(node, "auto_reference_names");
    if (autoWidget && !autoWidget.__buffAutoRefWrapped) {
      const oldCallback = autoWidget.callback;
      autoWidget.callback = function (...args) {
        const out = oldCallback?.apply(this, args);
        queueMicrotask(() => syncAutoReferenceManifest(node));
        return out;
      };
      autoWidget.__buffAutoRefWrapped = true;
    }

    // Cheap refresh on draw so renaming an already-connected upstream node is picked up
    // without forcing the user to disconnect/reconnect the image.
    const origDrawForeground = node.onDrawForeground?.bind(node);
    node.onDrawForeground = function (...args) {
      const out = origDrawForeground?.(...args);
      syncAutoReferenceManifest(node);
      return out;
    };

    queueMicrotask(() => refreshReferences(node));
  },
});
