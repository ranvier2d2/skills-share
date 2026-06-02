#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";

function usage() {
  console.error("Usage: node run_aead_matrix.mjs <config.json>");
  process.exit(1);
}

const configPath = process.argv[2];
if (!configPath) usage();

const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const ciphertextEncoding = config.ciphertextEncoding ?? "base64";
const payload = Buffer.from(config.ciphertext, ciphertextEncoding);

const framings = config.framings ?? ["direct12", "salt16_nonce12"];
const algorithms = config.algorithms ?? [
  "aes-128-gcm",
  "aes-192-gcm",
  "aes-256-gcm",
  "chacha20-poly1305",
];
const derivations = config.derivations ?? [
  "sha256",
  "sha512-32",
  "pbkdf2-sha1-10000",
  "pbkdf2-sha256-10000",
  "pbkdf2-sha256-100000",
  "scrypt",
];
const secrets = config.secrets ?? [];
const salts = config.salts ?? [""];
const aads = config.aads ?? [""];

if (!secrets.length) {
  console.error("Config must include a non-empty `secrets` array.");
  process.exit(1);
}

function keyLengthFor(algo) {
  if (algo === "aes-128-gcm") return 16;
  if (algo === "aes-192-gcm") return 24;
  return 32;
}

function framingParts(frame) {
  if (frame === "direct12") {
    return {
      nonce: payload.subarray(0, 12),
      ciphertext: payload.subarray(12, payload.length - 16),
      tag: payload.subarray(payload.length - 16),
      extraSalt: Buffer.alloc(0),
    };
  }
  if (frame === "salt16_nonce12") {
    return {
      extraSalt: payload.subarray(0, 16),
      nonce: payload.subarray(16, 28),
      ciphertext: payload.subarray(28, payload.length - 16),
      tag: payload.subarray(payload.length - 16),
    };
  }
  throw new Error(`Unknown framing: ${frame}`);
}

function derive(secret, saltBuf, method, keyLen) {
  if (method === "sha256") {
    return crypto.createHash("sha256").update(secret).digest().subarray(0, keyLen);
  }
  if (method === "sha512-32") {
    return crypto.createHash("sha512").update(secret).digest().subarray(0, keyLen);
  }
  if (method === "pbkdf2-sha1-10000") {
    return crypto.pbkdf2Sync(secret, saltBuf, 10000, keyLen, "sha1");
  }
  if (method === "pbkdf2-sha256-10000") {
    return crypto.pbkdf2Sync(secret, saltBuf, 10000, keyLen, "sha256");
  }
  if (method === "pbkdf2-sha256-100000") {
    return crypto.pbkdf2Sync(secret, saltBuf, 100000, keyLen, "sha256");
  }
  if (method === "scrypt") {
    return crypto.scryptSync(secret, saltBuf.length ? saltBuf : Buffer.from("salt"), keyLen);
  }
  throw new Error(`Unknown derivation: ${method}`);
}

function tryDecrypt(algo, key, nonce, ciphertext, tag, aad) {
  try {
    const opts =
      algo === "chacha20-poly1305" ? { authTagLength: 16 } : undefined;
    const decipher = opts
      ? crypto.createDecipheriv(algo, key, nonce, opts)
      : crypto.createDecipheriv(algo, key, nonce);
    if (aad) decipher.setAAD(Buffer.from(aad));
    decipher.setAuthTag(tag);
    const plaintext = Buffer.concat([
      decipher.update(ciphertext),
      decipher.final(),
    ]);
    return {
      plaintextUtf8: plaintext.toString("utf8"),
      plaintextHex: plaintext.toString("hex"),
    };
  } catch {
    return null;
  }
}

let total = 0;
const hits = [];
for (const frame of framings) {
  const parts = framingParts(frame);
  for (const secret of secrets) {
    for (const salt of salts) {
      const saltBuf = Buffer.concat([parts.extraSalt, Buffer.from(salt)]);
      for (const derivation of derivations) {
        for (const algorithm of algorithms) {
          const key = derive(secret, saltBuf, derivation, keyLengthFor(algorithm));
          for (const aad of aads) {
            total += 1;
            const hit = tryDecrypt(
              algorithm,
              key,
              parts.nonce,
              parts.ciphertext,
              parts.tag,
              aad,
            );
            if (hit) {
              hits.push({
                frame,
                secret,
                salt,
                aad,
                derivation,
                algorithm,
                ...hit,
              });
            }
          }
        }
      }
    }
  }
}

console.log(JSON.stringify({ total, hits }, null, 2));
