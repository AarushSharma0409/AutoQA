"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import {
  ArrowUpRight,
  Download,
  FileText,
  LoaderCircle,
  X,
} from "lucide-react";
import {
  Api,
  FilePreview,
  StoredFile,
  bytesLabel,
  safeUrl,
} from "../lib/types";

export function useFile(file: StoredFile | undefined, api: Api) {
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [error, setError] = useState("");
  const identity = file ? JSON.stringify(file) : "";
  useEffect(() => {
    if (!identity) return;
    const file: StoredFile = JSON.parse(identity);
    const controller = new AbortController();
    let objectUrl: string | undefined;
    void (async () => {
      try {
        const response = await api(`/files/${file.id}`, {
          signal: controller.signal,
        });
        const blob = await response.blob();
        const text =
          file.mime.startsWith("text/") || file.mime === "application/json"
            ? await blob.text()
            : undefined;
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setPreview({ file, url: objectUrl, text });
        setError("");
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    })();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [identity, api]);
  return { preview: preview?.file.id === file?.id ? preview : null, error };
}

export function MarkdownContent({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        skipHtml
        allowedElements={[
          "p",
          "h1",
          "h2",
          "h3",
          "h4",
          "ul",
          "ol",
          "li",
          "strong",
          "em",
          "code",
          "pre",
          "blockquote",
          "a",
          "hr",
          "br",
        ]}
        components={{
          a: ({ href, children }) => (
            <a href={safeUrl(href || "")} target="_blank" rel="noreferrer">
              {children}
              <ArrowUpRight size={12} />
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function ReportView({ file, api }: { file: StoredFile; api: Api }) {
  const { preview, error } = useFile(file, api);
  if (error)
    return (
      <p className="inline-error" role="alert">
        {error}
      </p>
    );
  if (!preview)
    return (
      <div className="preview-loading">
        <LoaderCircle size={18} className="spin" /> Opening report…
      </div>
    );
  return <MarkdownContent text={preview.text || ""} />;
}

export function ChartView({ file, api }: { file: StoredFile; api: Api }) {
  const { preview, error } = useFile(file, api);
  if (error) return <p className="inline-error">{error}</p>;
  if (!preview)
    return (
      <div className="preview-loading">
        <LoaderCircle size={16} className="spin" /> Loading chart…
      </div>
    );
  return (
    <Image
      unoptimized
      src={preview.url}
      alt={file.name}
      width={800}
      height={500}
      className="generated-chart"
    />
  );
}

export function FileViewer({
  file,
  api,
  onClose,
  download,
}: {
  file: StoredFile;
  api: Api;
  onClose: () => void;
  download: (file: StoredFile) => void;
}) {
  const { preview, error } = useFile(file, api);
  return (
    <section className="file-viewer" aria-label={`Preview ${file.name}`}>
      <header>
        <div>
          <FileText size={18} />
          <strong>{file.name}</strong>
          <span>{bytesLabel(file.size)}</span>
        </div>
        <div>
          <button
            className="icon-button"
            aria-label={`Download preview ${file.name}`}
            onClick={() => download(file)}
          >
            <Download size={17} />
          </button>
          <button
            className="icon-button"
            aria-label="Close preview"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>
      </header>
      <div className="file-viewer-body">
        {error ? (
          <p role="alert">{error}</p>
        ) : !preview ? (
          <LoaderCircle className="spin" size={20} />
        ) : file.mime === "text/markdown" ? (
          <MarkdownContent text={preview.text || ""} />
        ) : preview.text !== undefined ? (
          <pre>{preview.text}</pre>
        ) : file.mime.startsWith("image/") ? (
          <Image
            unoptimized
            src={preview.url}
            alt={file.name}
            width={800}
            height={500}
            className="generated-chart"
          />
        ) : file.mime === "application/pdf" ? (
          <iframe src={preview.url} title="PDF report preview" />
        ) : file.name.toLowerCase().endsWith(".docx") ? (
          <div className="unavailable-preview">
            <FileText size={30} />
            <h3>Open this report in Word</h3>
            <p>Download an editable report with findings, tables, and source excerpts.</p>
            <button className="button primary" onClick={() => download(file)}>
              <Download size={16} /> Download Word document
            </button>
          </div>
        ) : (
          <div className="unavailable-preview">
            <FileText size={30} />
            <h3>Open this spreadsheet in Excel</h3>
            <p>
              The workbook includes the category totals and an editable chart.
            </p>
            <button className="button primary" onClick={() => download(file)}>
              <Download size={16} /> Download spreadsheet
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
