import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";

function findRepositoryRoot(start: string): string {
  let directory = start;
  while (!existsSync(join(directory, "pnpm-workspace.yaml"))) {
    const parent = dirname(directory);
    if (parent === directory) throw new Error(`No repository root above ${start}`);
    directory = parent;
  }
  return directory;
}

const repositoryRoot = findRepositoryRoot(process.cwd());

type BridgeResponse = { id: number; status: number; headers: Record<string, string>; body: string };

/**
 * Runs packages/api/scripts/asgi_stdio_bridge.py: the real FastAPI app and SQLite service in a
 * Python process, reached through stdin/stdout instead of a socket.
 */
export class AsgiBridge {
  private nextId = 1;
  private readonly pending = new Map<number, (response: BridgeResponse) => void>();

  private constructor(private readonly child: ChildProcessWithoutNullStreams) {}

  static async start(dataDir: string, env: Record<string, string> = {}): Promise<AsgiBridge> {
    const child = spawn("uv", ["run", "python", "packages/api/scripts/asgi_stdio_bridge.py"], {
      cwd: repositoryRoot,
      env: { ...process.env, GEO_COMPANION_DATA_DIR: dataDir, ...env },
    });
    const bridge = new AsgiBridge(child);
    let stderr = "";
    child.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
    const lines = createInterface({ input: child.stdout });
    await new Promise<void>((resolve, reject) => {
      child.once("exit", (code) => reject(new Error(`ASGI bridge exited with ${code}: ${stderr}`)));
      lines.on("line", (line) => {
        const message = JSON.parse(line) as BridgeResponse | { ready: true };
        if ("ready" in message) {
          resolve();
          return;
        }
        bridge.pending.get(message.id)?.(message);
        bridge.pending.delete(message.id);
      });
    });
    return bridge;
  }

  /** A fetch implementation whose requests are answered by the real API process. */
  readonly fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const id = this.nextId++;
    const url = new URL(String(input), "http://bridge");
    const body = init?.body instanceof Blob
      ? { body_base64: Buffer.from(await init.body.arrayBuffer()).toString("base64"), content_type: new Headers(init.headers).get("content-type") }
      : { body: typeof init?.body === "string" ? init.body : null };
    const reply = new Promise<BridgeResponse>((resolve) => this.pending.set(id, resolve));
    this.child.stdin.write(`${JSON.stringify({
      id,
      method: init?.method ?? "GET",
      path: `${url.pathname}${url.search}`,
      ...body,
    })}\n`);
    const response = await reply;
    const empty = response.status === 204 || response.body === "";
    return new Response(empty ? null : response.body, { status: response.status, headers: response.headers });
  };

  async stop(): Promise<void> {
    if (this.child.exitCode !== null) return;
    const exited = new Promise<void>((resolve) => this.child.once("exit", () => resolve()));
    this.child.stdin.end();
    await exited;
  }
}
