#!/usr/bin/env node

import { Buffer } from "node:buffer";

function usage() {
  console.error("Usage: node decode_text_clues.mjs <clue-text>");
  process.exit(1);
}

const clue = process.argv.slice(2).join(" ");
if (!clue) usage();

function rot13(s) {
  return s.replace(/[A-Za-z]/g, (c) => {
    const start = c <= "Z" ? 65 : 97;
    return String.fromCharCode(((c.charCodeAt(0) - start + 13) % 26) + start);
  });
}

function rot47(s) {
  return s.replace(/[!-~]/g, (c) =>
    String.fromCharCode(33 + ((c.charCodeAt(0) - 33 + 47) % 94)),
  );
}

function safeDecode(label, fn) {
  try {
    return [label, fn()];
  } catch {
    return null;
  }
}

const candidates = [
  ["original", clue],
  ["reverse", [...clue].reverse().join("")],
  ["rot13", rot13(clue)],
  ["rot47", rot47(clue)],
  ["reverse+rot13", rot13([...clue].reverse().join(""))],
  ["reverse+rot47", rot47([...clue].reverse().join(""))],
];

const extra = [
  safeDecode("decodeURIComponent", () => decodeURIComponent(clue)),
  safeDecode("base64", () => Buffer.from(clue, "base64").toString("utf8")),
  safeDecode("hex", () => Buffer.from(clue, "hex").toString("utf8")),
].filter(Boolean);

const result = Object.fromEntries([...candidates, ...extra]);
console.log(JSON.stringify(result, null, 2));
