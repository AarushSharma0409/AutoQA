"use client";

import { useState } from "react";
import { Api, Task, StoredFile, activeStates, statusLabel } from "../lib/types";
import { ReportView } from "./report-view";

export function ConversationHistory({
  task,
  api,
  download,
}: {
  task: Task;
  api: Api;
  download: (file: StoredFile) => Promise<void>;
}) {
  return (
    <div className="conversation-history">
      {(task.turns || []).map((turn, index) => {
        const files = (task.files || []).filter((f) =>
          turn.file_ids.includes(f.id),
        );
        const report = [...files]
          .reverse()
          .find((f) => f.mime === "text/markdown");
        return (
          <section className="conversation-turn" key={index}>
            <div className="conversation-message">
              <span>You · {index + 1}</span>
              <p>{turn.goal}</p>
            </div>
            <details className="previous-response">
              <summary>
                AutoAgent · {statusLabel(turn.status)}
                {report ? " · View report" : ""}
              </summary>
              {turn.error && <p role="note">{turn.error}</p>}
              {turn.summary && <p>{turn.summary}</p>}
              {report && <ReportView file={report} api={api} />}
              {files.map((file) => (
                <button
                  className="button quiet"
                  key={file.id}
                  onClick={() => void download(file)}
                >
                  Download {file.name}
                </button>
              ))}
            </details>
          </section>
        );
      })}
      <div className="conversation-message">
        <span>You · {(task.turns?.length || 0) + 1}</span>
        <p>{task.current_goal || task.goal}</p>
      </div>
    </div>
  );
}

export function FollowUpComposer({
  task,
  busy,
  send,
}: {
  task: Task;
  busy: boolean;
  send: (message: string) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState("");
  const active = activeStates.includes(task.status);
  return (
    <form
      className="follow-up-composer"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await send(draft)) setDraft("");
      }}
    >
      <label htmlFor="follow-up">Continue this conversation</label>
      <p>
        Your documents and previous results stay with this task. Each message
        starts a new run.
      </p>
      <textarea
        id="follow-up"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        maxLength={8000}
        rows={3}
        placeholder="Ask for changes, another chart, or more analysis…"
        disabled={busy}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            if (!active && !busy && draft.trim().length >= 3)
              e.currentTarget.form?.requestSubmit();
          }
        }}
      />
      <div>
        <span>
          {active
            ? "Wait for this run, or cancel it to change direction."
            : "Ctrl / ⌘ + Enter to send"}
        </span>
        <button
          className="button primary"
          type="submit"
          disabled={active || busy || draft.trim().length < 3}
        >
          {busy ? "Sending…" : "Send follow-up"}
        </button>
      </div>
    </form>
  );
}
