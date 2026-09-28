## The "Allow remote debugging?" prompt (macOS)

Each new CDP connection may make Helium show an "Allow remote debugging?" dialog. The connection waits for the person using Helium to approve it, and attach may time out after about 30 seconds. Have them approve the prompt directly in Helium while the connection is pending. If multiple prompts are visible, each corresponds to a pending connection; avoid opening more connections until the current one finishes.

- If approval comes after attach has timed out, retry the attach and approve its new prompt.
- If the prompt was approved but the WebSocket still does not answer `Browser.getVersion`, fully quit and relaunch Helium, then retry and approve the new prompt.

## Verify an attach worked

```bash
node -e '
const fs = require("fs"), os = require("os"), path = require("path");
const p = path.join(os.homedir(), "Library/Application Support/net.imput.helium/DevToolsActivePort");
const [port, wsPath] = fs.readFileSync(p, "utf8").trim().split("\n").map(s => s.trim());
const ws = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Browser.getVersion" }));
ws.onmessage = (e) => { console.log(e.data); process.exit(0); };
ws.onerror = (e) => { console.error("failed", e.message || e); process.exit(1); };
'
```

A `Browser.getVersion` response means the debug server is reachable and attachable. This check opens another CDP connection, so approve its prompt in Helium too.
