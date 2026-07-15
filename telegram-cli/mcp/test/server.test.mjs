import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const testDir = fileURLToPath(new URL(".", import.meta.url));
const serverPath = fileURLToPath(new URL("../server.mjs", import.meta.url));
const mockPath = join(testDir, "mock-telegram-cli");
const scratch = await mkdtemp(join(tmpdir(), "telegram-mcp-test-"));
const executeLog = join(scratch, "execute.log");
const client = new Client({ name: "telegram-mcp-test", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [serverPath],
  env: {
    ...process.env,
    TELEGRAM_CLI_PATH: mockPath,
    MOCK_EXECUTE_LOG: executeLog,
  },
});

try {
  await client.connect(transport);
  const listed = await client.listTools();
  assert.equal(listed.tools.length, 10);
  assert.equal(listed.tools.find((tool) => tool.name === "telegram_list_dialogs")?.annotations?.readOnlyHint, true);
  const executeTool = listed.tools.find((tool) => tool.name === "telegram_execute_prepared_action");
  assert.equal(executeTool?.annotations?.readOnlyHint, false);
  assert.equal(executeTool?.annotations?.destructiveHint, true);

  const dialogs = await client.callTool({ name: "telegram_list_dialogs", arguments: { limit: 1 } });
  assert.equal(dialogs.isError, undefined);

  const prepared = await client.callTool({
    name: "telegram_prepare_send",
    arguments: { chat: "Mock Chat", text: "hello" },
  });
  assert.equal(prepared.isError, undefined);
  const token = prepared.structuredContent.result.approval_token;
  assert.ok(token.length >= 20);

  await assert.rejects(readFile(executeLog, "utf8"));

  const invalid = await client.callTool({
    name: "telegram_execute_prepared_action",
    arguments: { approvalToken: "invalid-token-that-is-long-enough" },
  });
  assert.equal(invalid.isError, true);

  const executed = await client.callTool({
    name: "telegram_execute_prepared_action",
    arguments: { approvalToken: token },
  });
  assert.equal(executed.isError, undefined);
  const executeLogAfterFirstUse = (await readFile(executeLog, "utf8")).trim();
  assert.equal(executeLogAfterFirstUse, "send");

  const reused = await client.callTool({
    name: "telegram_execute_prepared_action",
    arguments: { approvalToken: token },
  });
  assert.equal(reused.isError, true);
  assert.equal((await readFile(executeLog, "utf8")).trim(), executeLogAfterFirstUse);

  console.log("telegram_mcp_tests=passed");
} finally {
  await client.close();
  await rm(scratch, { recursive: true, force: true });
}
