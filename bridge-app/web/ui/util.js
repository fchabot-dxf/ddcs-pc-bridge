// util.js — tiny DOM helpers (no framework). `el` builds elements; `toast` shows a transient message.
export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

export const clear = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };

export function toast(msg, bad = false) {
  const t = el("div", { class: "toast" + (bad ? " bad" : "") }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 3200);
}

export const fmtEta = (s) =>
  s === null || s === undefined ? "—"
  : s >= 60 ? `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`
  : `${s}s`;
