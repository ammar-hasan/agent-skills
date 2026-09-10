"use client";

import { useState } from "react";

export function CopyCommand({ command }: { command: string }) {
  const [status, setStatus] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setStatus("Command copied.");
    } catch {
      setStatus("Select the command above and copy it manually.");
    }
  }
  return (
    <div className="command">
      <code>{command}</code>
      <button type="button" onClick={copy} aria-label="Copy install command">
        {status === "Command copied." ? "Copied ✓" : "Copy"}
      </button>
      <span className="copy-status" role="status">
        {status}
      </span>
    </div>
  );
}
