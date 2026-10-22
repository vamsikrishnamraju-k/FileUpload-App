import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const MAX_SIZE = 200 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".zip"];

function isAllowedFile(file) {
  const name = file?.name?.toLowerCase() || "";
  return ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function escapeText(value) {
  return String(value ?? "");
}

function App() {
  const fileInput = useRef(null);
  const [selected, setSelected] = useState([]);
  const [folderName, setFolderName] = useState("");
  const [message, setMessage] = useState({ text: "", type: "" });
  const [files, setFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const showMessage = (text, type = "") => setMessage({ text, type });

  const selectFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) {
      setSelected([]);
      return;
    }

    const invalid = files.find((file) => !isAllowedFile(file));
    if (invalid) {
      setSelected([]);
      showMessage(`${invalid.name}: only PDF and ZIP files are allowed.`, "error");
      if (fileInput.current) fileInput.current.value = "";
      return;
    }

    const oversized = files.find((file) => file.size > MAX_SIZE);
    if (oversized) {
      setSelected([]);
      showMessage(`${oversized.name}: file exceeds the 200 MB limit.`, "error");
      if (fileInput.current) fileInput.current.value = "";
      return;
    }

    setSelected(files);
    showMessage("");
  };

  const loadFiles = async () => {
    setLoadingFiles(true);
    try {
      const response = await fetch("/api/files");
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Could not load files");
      setFiles(Array.isArray(data) ? data : (data.files || []));
    } catch (err) {
      setFiles([]);
      showMessage(err.message, "error");
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const upload = async () => {
    if (!selected.length || uploading) return;
    if (!folderName.trim()) {
      showMessage("Enter a folder name first.", "error");
      return;
    }

    const invalid = selected.find((file) => !isAllowedFile(file));
    if (invalid) {
      showMessage(`${invalid.name}: only PDF and ZIP files are allowed.`, "error");
      return;
    }
    const oversized = selected.find((file) => file.size > MAX_SIZE);
    if (oversized) {
      showMessage(`${oversized.name}: file exceeds the 200 MB limit.`, "error");
      return;
    }

    const form = new FormData();
    form.append("folderName", folderName.trim());
    selected.forEach((file) => form.append("file", file));

    setUploading(true);
    showMessage("Uploading files to S3…");

    try {
      const response = await fetch("/api/upload", { method: "POST", body: form });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Upload failed");

      showMessage(`Upload successful — ${data.files?.length || selected.length} file(s) stored in S3.`, "success");
      setSelected([]);
      setFolderName("");
      if (fileInput.current) fileInput.current.value = "";
      await loadFiles();
    } catch (err) {
      showMessage(err.message, "error");
    } finally {
      setUploading(false);
    }
  };

  const download = async (key) => {
    try {
      const response = await fetch(`/api/download/${encodeURIComponent(key)}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Download failed");
      window.open(data.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      showMessage(err.message, "error");
    }
  };

  const remove = async (key) => {
    if (!window.confirm("Delete this file from S3?")) return;

    try {
      const response = await fetch(`/api/delete/${encodeURIComponent(key)}`, {
        method: "DELETE",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Delete failed");
      showMessage("File deleted successfully from S3.", "success");
      await loadFiles();
    } catch (err) {
      showMessage(err.message, "error");
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragOver(false);
    selectFiles(event.dataTransfer.files);
  };

  return (
    <>
      <header className="topbar">
        <div className="brand"><span className="brand-mark">☁</span><span>CloudDrop</span></div>
        <nav><a className="active" href="#home">Home</a><a href="#upload">Upload</a><a href="#activity">Activity</a></nav>
        <div className="status"><span className="dot"></span> S3 Storage</div>
      </header>

      <main id="home">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">CLOUD FILE MANAGER</div>
            <h1>Upload. Store.<br /><span>Access.</span></h1>
            <p>React frontend for your Flask + S3 file-upload application. Only PDF and ZIP files up to 200 MB are accepted.</p>
            <a className="primary-btn" href="#upload">Start uploading <span>→</span></a>
          </div>
          <div className="hero-art">
            <div className="cloud">☁</div>
            <div className="mini-card c1">S3<br /><strong>Storage</strong></div>
            <div className="mini-card c2">🔒<br /><strong>Secure</strong></div>
            <div className="mini-card c3">⚡<br /><strong>Fast</strong></div>
          </div>
        </section>

        <section className="stats">
          <div><span>01</span><strong>React frontend</strong><p>Modern component UI</p></div>
          <div><span>02</span><strong>S3 storage</strong><p>Files go to your bucket</p></div>
          <div><span>03</span><strong>File validation</strong><p>PDF / ZIP only</p></div>
          <div><span>04</span><strong>200 MB limit</strong><p>Checked before S3</p></div>
        </section>

        <section className="workspace" id="upload">
          <div className="section-heading">
            <div><div className="eyebrow">YOUR STORAGE</div><h2>Upload a file</h2></div>
            <span className="backend-badge">● Backend API connected</span>
          </div>

          <div
            className={`upload-card ${dragOver ? "over" : ""}`}
            onDragEnter={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="upload-icon">↑</div>
            <h3>Drop your PDF or ZIP files here</h3>
            <p>Multiple files allowed · Maximum 200 MB per file</p>
            <label className="choose-btn" htmlFor="fileInput">Choose files</label>
            <input
              id="fileInput"
              ref={fileInput}
              type="file"
              accept=".pdf,.zip,application/pdf,application/zip"
              multiple
              hidden
              onChange={(e) => selectFiles(e.target.files)}
            />
            <label className="folder-label">Folder name</label>
            <input
              className="folder-input"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="e.g. prod-files"
            />
            <div className="selected">
              {selected.length
                ? selected.map((file) => `${file.name} · ${formatSize(file.size)}`).join(" | ")
                : "No files selected"}
            </div>
            <button className="upload-btn" disabled={!selected || uploading} onClick={upload}>
              {uploading ? "Uploading…" : "Upload files to S3"}
            </button>
            <div className={`message ${message.type}`}>{message.text}</div>
          </div>
        </section>

        <section className="activity" id="activity">
          <div className="section-heading">
            <div><div className="eyebrow">S3 ACTIVITY</div><h2>Recent uploads</h2></div>
            <button className="ghost-btn" onClick={loadFiles}>Refresh</button>
          </div>
          <div className="file-list">
            {loadingFiles ? (
              <div className="empty">Loading files…</div>
            ) : !files.length ? (
              <div className="empty">No files uploaded yet.</div>
            ) : (
              Object.entries(files.reduce((groups, file) => {
                const key = `${file.upload_id || "legacy"}:${file.folder_name || "legacy"}`;
                (groups[key] ||= []).push(file);
                return groups;
              }, {})).map(([groupKey, group]) => (
                <div className="file-group" key={groupKey}>
                  <h3>{escapeText(group[0].folder_name || "legacy")}</h3>
                  {group.map((file) => (
                    <div className="file-row" key={file.id ?? file.s3_key}>
                      <div className="file-icon">↗</div>
                      <div className="file-name">{escapeText(file.file_name || file.s3_key)}</div>
                      <div className="file-time">{formatDate(file.uploaded_at)}</div>
                      <button className="ghost-btn" onClick={() => download(file.s3_key)}>Download</button>
                      <button className="ghost-btn delete-btn" onClick={() => remove(file.s3_key)}>Delete</button>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
          <p className="note">Only PDF and ZIP files are accepted by both the React frontend and Flask backend. Invalid files are rejected before the S3 PutObject call.</p>
        </section>
      </main>

      <footer>CloudDrop · React · Node.js · Flask · Amazon S3 · EKS</footer>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
