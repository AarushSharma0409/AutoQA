import { cpSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const standalone = join(root, ".next", "standalone");
const server = join(standalone, "server.js");
if (!existsSync(server)) {
  throw new Error("Build AutoAgent first with npm run build.");
}
for (const path of ["public", ".next/static"]) {
  cpSync(join(root, path), join(standalone, path), {
    recursive: true,
    force: true,
  });
}
process.env.HOSTNAME = process.env.AUTOAGENT_HOST || "127.0.0.1";
await import(pathToFileURL(server).href);
