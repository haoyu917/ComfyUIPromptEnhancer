import { app } from "../../scripts/app.js";

const CLASS_NAMES = new Set(["BUFF_AITextPreview", "BUFF_AIAPITest"]);
const DOM_MARGIN = 10;

function firstValue(value, fallback = "") {
  if (Array.isArray(value)) return value.length ? value[0] : fallback;
  return value ?? fallback;
}

function isVueNodesMode() {
  return globalThis?.LiteGraph?.vueNodesMode === true;
}

function fitNode(node, minWidth, bottomPadding = 10) {
  const apply = () => {
    try {
      const measured = node.computeSize?.();
      const width = Math.max(Number(node.size?.[0]) || 0, Number(measured?.[0]) || 0, minWidth);
      const height = Math.max(Number(measured?.[1]) || 0, 180) + bottomPadding;
      // Static debug nodes are safe to fit explicitly in legacy mode.  In Vue mode
      // the DOM/ResizeObserver is the source of truth; arrange() is enough.
      if (isVueNodesMode()) {
        node.arrange?.();
      } else {
        node.setSize?.([width, height]);
        node.arrange?.();
      }
      node.setDirtyCanvas?.(true, true);
    } catch (error) {
      console.debug("BUFF AI: debug node fit skipped", error);
    }
  };
  apply();
  requestAnimationFrame(() => {
    apply();
    requestAnimationFrame(apply);
  });
  window.setTimeout(apply, 120);
}

function buildPreviewDOM(node, isApiTest) {
  const contentHeight = isApiTest ? 190 : 330;
  const rowHeight = contentHeight + DOM_MARGIN * 2;

  const root = document.createElement("div");
  root.style.display = "flex";
  root.style.flexDirection = "column";
  root.style.gap = "6px";
  root.style.width = "100%";
  root.style.height = `${contentHeight}px`;
  root.style.minHeight = `${contentHeight}px`;
  root.style.maxHeight = `${contentHeight}px`;
  root.style.maxWidth = "100%";
  root.style.boxSizing = "border-box";
  root.style.overflow = "hidden";
  root.style.padding = "2px";

  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.alignItems = "center";
  header.style.justifyContent = "space-between";
  header.style.gap = "8px";
  header.style.height = "24px";
  header.style.minHeight = "24px";
  header.style.flex = "0 0 24px";

  const titleEl = document.createElement("div");
  titleEl.textContent = isApiTest ? "API 连接测试" : "提示词预览";
  titleEl.style.fontSize = "12px";
  titleEl.style.fontWeight = "600";
  titleEl.style.opacity = "0.92";
  titleEl.style.overflow = "hidden";
  titleEl.style.textOverflow = "ellipsis";
  titleEl.style.whiteSpace = "nowrap";
  header.appendChild(titleEl);

  const copyButton = document.createElement("button");
  copyButton.textContent = "复制";
  copyButton.style.fontSize = "11px";
  copyButton.style.lineHeight = "18px";
  copyButton.style.height = "22px";
  copyButton.style.padding = "1px 8px";
  copyButton.style.cursor = "pointer";
  copyButton.style.flex = "0 0 auto";
  header.appendChild(copyButton);
  root.appendChild(header);

  const textarea = document.createElement("textarea");
  textarea.readOnly = true;
  textarea.placeholder = isApiTest ? "运行后显示 API 连接结果。" : "运行工作流后，这里会显示 BUFF AI 输出的文本。";
  textarea.style.display = "block";
  textarea.style.width = "100%";
  textarea.style.maxWidth = "100%";
  textarea.style.minWidth = "0";
  textarea.style.height = "auto";
  textarea.style.minHeight = "0";
  textarea.style.flex = "1 1 auto";
  textarea.style.boxSizing = "border-box";
  textarea.style.margin = "0";
  textarea.style.padding = "8px";
  textarea.style.borderRadius = "4px";
  textarea.style.resize = "none";
  textarea.style.overflow = "auto";
  textarea.style.fontFamily = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
  textarea.style.fontSize = "12px";
  textarea.style.lineHeight = "1.45";
  textarea.style.whiteSpace = "pre-wrap";
  textarea.style.wordBreak = "break-word";
  root.appendChild(textarea);

  copyButton.onclick = async (event) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(textarea.value || "");
      const old = copyButton.textContent;
      copyButton.textContent = "已复制";
      window.setTimeout(() => { copyButton.textContent = old; }, 900);
    } catch (error) {
      console.warn("BUFF AI: copy preview failed", error);
    }
  };

  const widget = node.addDOMWidget("buff_text_preview", "BUFF_TEXT_PREVIEW", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => rowHeight,
    getMaxHeight: () => rowHeight,
    getHeight: () => rowHeight,
  });
  if (widget) {
    widget.computedHeight = rowHeight;
    widget.__buffPreviewRowHeight = rowHeight;
  }

  return { textarea, titleEl, rowHeight };
}

app.registerExtension({
  name: "buff_ai.text_preview",
  async nodeCreated(node) {
    if (!CLASS_NAMES.has(node.comfyClass)) return;

    const isApiTest = node.comfyClass === "BUFF_AIAPITest";
    let textarea = null;
    let titleEl = null;

    const textInput = node.inputs?.find((input) => input?.name === "text");
    if (textInput) textInput.label = "文本";

    if (typeof node.addDOMWidget === "function") {
      const built = buildPreviewDOM(node, isApiTest);
      textarea = built.textarea;
      titleEl = built.titleEl;
    } else if (typeof node.addWidget === "function") {
      const fallback = node.addWidget("text", isApiTest ? "API 连接结果" : "提示词预览", "", null, { multiline: true });
      fallback.serialize = false;
      textarea = {
        get value() { return fallback.value || ""; },
        set value(v) { fallback.value = String(v || ""); },
      };
    }

    const originalExecuted = node.onExecuted?.bind(node);
    node.onExecuted = function (message) {
      const result = originalExecuted?.(message);
      const text = String(firstValue(message?.text, "") || "");
      const title = String(firstValue(message?.preview_title, isApiTest ? "API 连接测试" : "提示词预览") || "");
      if (textarea) textarea.value = text;
      if (titleEl) titleEl.textContent = title;
      node.setDirtyCanvas?.(true, true);
      return result;
    };

    // Keep the DOM preview inside the node body.  The old implementation hard-coded
    // a 320px textarea without reserving a matching ComfyUI widget row, which is why
    // both Text Preview and API Test visually overflowed their nodes.
    fitNode(node, isApiTest ? 440 : 520, 12);
  },
});
