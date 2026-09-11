export type StoredFile = {
  id: string;
  name: string;
  mime: string;
  size: number;
  kind: string;
};
export type Source = {
  id: string;
  title: string;
  url: string;
  excerpt: string;
  fixture: boolean;
};
export type Task = {
  id: string;
  goal: string;
  mode: string;
  status: string;
  created: number;
  updated: number;
  error?: string;
  files?: StoredFile[];
  sources?: Source[];
  artifact_count?: number;
  current_goal?: string;
  current_file_ids?: string[] | null;
  turns?: {
    goal: string;
    status: string;
    summary: string;
    error?: string;
    file_ids: string[];
    created: number;
  }[];
  accounting_note?: string;
  usage?: { steps: number; tokens: number; cost: number; elapsed: number };
  approval?: {
    digest: string;
    approved: boolean | null;
    reason: string;
    decision: { tool: string; arguments: Record<string, unknown> };
  };
};
export type RunEvent = {
  id: number;
  kind: string;
  created: number;
  payload: {
    summary?: string;
    status?: string;
    tool?: string;
    mode?: string;
    output?: Record<string, unknown>;
    step?: number;
  };
};
export type Config = {
  mode: string;
  model: string;
  limits: {
    steps: number;
    tokens: number;
    seconds: number;
    cost: number;
    upload_bytes: number;
  };
  search_configured: boolean;
};
export type FilePreview = { file: StoredFile; url: string; text?: string };
export type Api = (path: string, init?: RequestInit) => Promise<Response>;
export const activeStates = ["queued", "running", "awaiting_approval"];
export const terminalStates = [
  "completed",
  "failed",
  "canceled",
  "awaiting_approval",
];
export const statusLabel = (status: string) =>
  ({
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    canceled: "Canceled",
    awaiting_approval: "Needs approval",
  })[status] || status;
export const taskLabel = (goal: string) =>
  goal.length > 84 ? goal.slice(0, 81).replace(/\s+\S*$/, "") + "…" : goal;
export const bytesLabel = (bytes: number) =>
  bytes >= 1_000_000
    ? `${(bytes / 1_000_000).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1000))} KB`;
export const safeUrl = (url: string) => {
  try {
    const parsed = new URL(url);
    return ["http:", "https:"].includes(parsed.protocol)
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
};
