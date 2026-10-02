/**
 * Fail if the committed SDK types are not what the schema generates (B09).
 *
 * The handwritten client drifted from the backend and nothing noticed, because
 * nothing compared them. This regenerates into a temporary file and diffs: a
 * renamed route fails the frontend job until the SDK is regenerated, which is
 * acceptance test 1 for this issue.
 */

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SCHEMA = "../contracts/openapi.json";
const COMMITTED = "packages/sdk/src/generated/schema.ts";

const scratch = mkdtempSync(join(tmpdir(), "clarity-sdk-"));
const fresh = join(scratch, "schema.ts");

try {
  execFileSync("npx", ["openapi-typescript", SCHEMA, "-o", fresh], {
    stdio: ["ignore", "ignore", "inherit"],
  });

  const current = readFileSync(COMMITTED, "utf8");
  const generated = readFileSync(fresh, "utf8");

  if (current !== generated) {
    console.error(
      [
        "",
        `The committed SDK types are stale: ${COMMITTED}`,
        "",
        "The backend's OpenAPI schema has changed since they were generated.",
        "Regenerate and commit the result:",
        "",
        "    make contracts        # re-export contracts/openapi.json",
        "    npm run sdk:generate  # regenerate the types",
        "",
      ].join("\n"),
    );
    process.exit(1);
  }

  console.log("SDK types match the committed OpenAPI schema.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
