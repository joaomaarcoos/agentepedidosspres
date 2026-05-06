import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const PYTHON_EXECUTABLE = process.env.PYTHON_EXECUTABLE || "python";
const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;

function resolveProjectRoot() {
  const cwd = process.cwd();
  if (existsSync(path.join(cwd, "execution"))) {
    return cwd;
  }

  return path.resolve(cwd, "..");
}

export async function runPythonJson<T>(
  scriptRelativePath: string,
  args: string[],
  options?: { timeoutMs?: number }
): Promise<T> {
  const projectRoot = resolveProjectRoot();
  const scriptPath = path.join(projectRoot, scriptRelativePath);
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  return new Promise<T>((resolve, reject) => {
    const child = spawn(PYTHON_EXECUTABLE, [scriptPath, ...args], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        PYTHONUTF8: "1",
      },
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });

    child.on("close", (code) => {
      clearTimeout(timeout);

      if (timedOut) {
        reject(new Error(`Python script timed out after ${timeoutMs}ms`));
        return;
      }

      const trimmedStdout = stdout.trim();
      if (!trimmedStdout) {
        reject(new Error(stderr.trim() || `Python script exited with code ${code}`));
        return;
      }

      try {
        const payload = JSON.parse(trimmedStdout) as T;
        if (code && code !== 0) {
          reject(new Error(stderr.trim() || `Python script exited with code ${code}`));
          return;
        }

        resolve(payload);
      } catch (error) {
        reject(
          new Error(
            `Invalid JSON from Python script: ${trimmedStdout}\n${stderr.trim() || String(error)}`
          )
        );
      }
    });
  });
}
