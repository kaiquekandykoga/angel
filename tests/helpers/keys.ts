import { generateKeyPairSync } from "node:crypto";

let cached: { privateKey: string; publicKey: string } | undefined;

export function rsaKeyPair(): { privateKey: string; publicKey: string } {
  if (cached === undefined) {
    const { privateKey, publicKey } = generateKeyPairSync("rsa", {
      modulusLength: 2048,
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
      publicKeyEncoding: { type: "spki", format: "pem" },
    });
    cached = { privateKey, publicKey };
  }
  return cached;
}
