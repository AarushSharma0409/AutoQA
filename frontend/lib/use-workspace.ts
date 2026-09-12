"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Config, RunEvent, StoredFile, Task, terminalStates } from "./types";

export function useWorkspace(getAccessToken?: () => Promise<string>) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [goal, setGoal] = useState("");
  const [uploads, setUploads] = useState<StoredFile[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState<
    "connecting" | "online" | "offline" | "unauthorized"
  >("connecting");
  const [config, setConfig] = useState<Config | null>(null);
  const [token, setToken] = useState("");
  const session = useRef(0);
  const selection = useRef<string | null>(null);
  const eventTask = useRef<Task | null>(null);
  const goalInput = useRef<HTMLTextAreaElement>(null);
  const uploadInput = useRef<HTMLInputElement>(null);

  const api = useCallback(
    async (path: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      const accessToken = getAccessToken ? await getAccessToken() : token;
      if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
      const response = await fetch("/api" + path, {
        ...init,
        headers,
        cache: "no-store",
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({
          detail: `The service returned ${response.status}.`,
        }));
        const error = new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Check the submitted fields.",
        ) as Error & { status: number };
        error.status = response.status;
        throw error;
      }
      return response;
    },
    [token, getAccessToken],
  );

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const currentSession = session.current;
      const currentSelection = selected;
      try {
        const [history, configuration] = await Promise.all([
          api("/tasks", { signal }).then((r) => r.json()),
          api("/config", { signal }).then((r) => r.json()),
        ]);
        if (signal?.aborted || currentSession !== session.current) return;
        setTasks(history);
        setConfig(configuration);
        setConnection("online");
        if (currentSelection) {
          const detail = await api(`/tasks/${currentSelection}`, {
            signal,
          }).then((r) => r.json());
          if (
            !signal?.aborted &&
            currentSession === session.current &&
            selection.current === currentSelection
          ) {
            eventTask.current = detail;
            setTask(detail);
          }
        }
      } catch (e) {
        if (signal?.aborted || currentSession !== session.current) return;
        if (
          currentSelection &&
          (e as Error & { status?: number }).status === 404 &&
          selection.current === currentSelection
        ) {
          selection.current = null;
          eventTask.current = null;
          setSelected(null);
          setTask(null);
          setEvents([]);
          window.history.replaceState({}, "", "/");
          setError(
            "This task is unavailable or belongs to a different workspace.",
          );
          setConnection("online");
          return;
        }
        setConnection(
          (e as Error & { status?: number }).status === 401
            ? "unauthorized"
            : "offline",
        );
      }
    },
    [api, selected],
  );

  function choose(id: string | null, updateUrl = true) {
    selection.current = id;
    eventTask.current = null;
    setSelected(id);
    setTask(null);
    setEvents([]);
    setError("");
    if (updateUrl)
      window.history.pushState(
        {},
        "",
        id ? `/?task=${encodeURIComponent(id)}` : "/",
      );
  }

  useEffect(() => {
    const restore = () =>
      choose(new URLSearchParams(window.location.search).get("task"), false);
    const initial = setTimeout(restore, 0);
    window.addEventListener("popstate", restore);
    return () => {
      clearTimeout(initial);
      window.removeEventListener("popstate", restore);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timeout: ReturnType<typeof setTimeout>;
    const poll = async () => {
      await refresh(controller.signal);
      if (!controller.signal.aborted) timeout = setTimeout(poll, 2500);
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let cursor = 0;
    let timeout: ReturnType<typeof setTimeout>;
    const connect = async () => {
      try {
        const response = await api(
          `/tasks/${selected}/events?after=${cursor}`,
          { signal: controller.signal },
        );
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";
          for (const block of blocks) {
            const data = block
              .split("\n")
              .find((line) => line.startsWith("data: "));
            if (!data || controller.signal.aborted) continue;
            const event: RunEvent = JSON.parse(data.slice(6));
            cursor = Math.max(cursor, event.id);
            setEvents((old) =>
              old.some((e) => e.id === event.id) ? old : [...old, event],
            );
          }
        }
      } catch {
        // Polling owns connection status; SSE resumes at its last persisted event ID.
      }
      if (!controller.signal.aborted)
        timeout = setTimeout(
          connect,
          terminalStates.includes(eventTask.current?.status || "")
            ? 15000
            : 1000,
        );
    };
    void connect();
    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [selected, api]);

  async function attach(files: FileList | File[] | null) {
    if (!files?.length || busy) return;
    setBusy(true);
    setError("");
    const generation = session.current;
    try {
      if (uploads.length + files.length > 10)
        throw new Error("Attach up to 10 files per task.");
      for (const file of Array.from(files)) {
        if (file.size > (config?.limits.upload_bytes || 10000000))
          throw new Error(`${file.name} exceeds the upload limit.`);
        const form = new FormData();
        form.append("file", file);
        const result = await api("/uploads", {
          method: "POST",
          body: form,
        }).then((r) => r.json());
        if (generation === session.current)
          setUploads((old) => [...old, result]);
        else return;
      }
    } catch (e) {
      if (generation === session.current) setError((e as Error).message);
    } finally {
      if (generation === session.current) setBusy(false);
      if (uploadInput.current) uploadInput.current.value = "";
    }
  }

  async function loadSample() {
    try {
      const response = await fetch("/examples/sales.csv");
      if (!response.ok) throw new Error("The sample file could not be loaded.");
      await attach([
        new File([await response.blob()], "sales.csv", { type: "text/csv" }),
      ]);
      setGoal(
        "Analyze this sales CSV, identify the three weakest-performing categories, research relevant market context, and generate a report with charts and suggested experiments.",
      );
      goalInput.current?.focus();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function submit() {
    if (busy || goal.trim().length < 3) {
      goalInput.current?.focus();
      return;
    }
    setBusy(true);
    setError("");
    const generation = session.current;
    try {
      const result = await api("/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, file_ids: uploads.map((f) => f.id) }),
      }).then((r) => r.json());
      if (generation !== session.current) return;
      choose(result.id);
      setTask(result);
      setGoal("");
      setUploads([]);
      setTasks((old) => [result, ...old.filter((t) => t.id !== result.id)]);
    } catch (e) {
      if (generation === session.current) setError((e as Error).message);
    } finally {
      if (generation === session.current) setBusy(false);
    }
  }

  async function control(action: string, body?: unknown) {
    if (busy) return;
    setBusy(true);
    setError("");
    const generation = session.current;
    try {
      await api(`/tasks/${selected}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (generation === session.current) await refresh();
    } catch (e) {
      if (generation === session.current) setError((e as Error).message);
    } finally {
      if (generation === session.current) setBusy(false);
    }
  }

  async function followUp(message: string): Promise<boolean> {
    if (busy || !selected || message.trim().length < 3) return false;
    const target = selected;
    const generation = session.current;
    setBusy(true);
    setError("");
    try {
      await api(`/tasks/${target}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: message, file_ids: [] }),
      });
      if (generation === session.current && selection.current === target)
        await refresh();
      return true;
    } catch (e) {
      if (generation === session.current && selection.current === target)
        setError((e as Error).message);
      return false;
    } finally {
      if (generation === session.current) setBusy(false);
    }
  }

  async function download(file: StoredFile) {
    try {
      const blob = await api(`/files/${file.id}`).then((r) => r.blob());
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function applyToken(value: string) {
    session.current += 1;
    setToken(value);
    setBusy(false);
    setTasks([]);
    setUploads([]);
    setConfig(null);
    setConnection("connecting");
    choose(null);
  }

  async function deleteFile(file: StoredFile) {
    if (busy || !window.confirm(`Permanently delete ${file.name}? This cannot be undone. Other files and your conversation will remain.`)) return;
    const generation = session.current;
    setBusy(true);
    setError("");
    try {
      await api(`/files/${file.id}`, { method: "DELETE" });
      if (generation === session.current) await refresh();
    } catch (error) {
      if (generation === session.current) setError((error as Error).message);
    } finally {
      if (generation === session.current) setBusy(false);
    }
  }

  return {
    tasks,
    selected,
    task,
    events,
    goal,
    setGoal,
    uploads,
    setUploads,
    busy,
    error,
    setError,
    connection,
    config,
    api,
    goalInput,
    uploadInput,
    choose,
    refresh,
    attach,
    loadSample,
    submit,
    control,
    followUp,
    download,
    deleteFile,
    applyToken,
  };
}
