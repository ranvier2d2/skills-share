#!/usr/bin/env node

import { Buffer } from "node:buffer";

function usage() {
  console.error("Usage: node probe_payload.mjs <payload>");
  process.exit(1);
}

const payload = process.argv.slice(2).join(" ").trim();
if (!payload) usage();

function isBase64(s) {
  return /^[A-Za-z0-9+/=]+$/.test(s) && s.length % 4 === 0;
}

function isBase64Url(s) {
  return /^[A-Za-z0-9\\-_]+={0,2}$/.test(s) && s.length % 4 === 0;
}

function isHex(s) {
  return /^[0-9a-fA-F]+$/.test(s) && s.length % 2 === 0;
}

function isBase32(s) {
  return /^[A-Z2-7=]+$/i.test(s) && s.length % 8 === 0;
}

function previewBytes(buf) {
  return {
    bytes: buf.length,
    first16: buf.subarray(0, 16).toString("hex"),
    last16: buf.subarray(Math.max(0, buf.length - 16)).toString("hex"),
  };
}

const out = {
  inputLength: payload.length,
  hasSpaces: /\\s/.test(payload),
  likely: {
    base64: isBase64(payload),
    base64url: isBase64Url(payload),
    hex: isHex(payload),
    base32: isBase32(payload),
  },
};

if (out.likely.base64) {
  try {
    out.base64 = previewBytes(Buffer.from(payload, "base64"));
  } catch {}
}

if (out.likely.base64url) {
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    out.base64url = previewBytes(Buffer.from(normalized, "base64"));
  } catch {}
}

if (out.likely.hex) {
  try {
    out.hex = previewBytes(Buffer.from(payload, "hex"));
  } catch {}
}

console.log(JSON.stringify(out, null, 2));
