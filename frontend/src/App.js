import React, { useState } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000";
const NAV = ["Upload", "About", "Soochi For You"];

function Nav({ page, setPage, onSessionSelect }) {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [sessions, setSessions] = React.useState([]);

  const handleDeleteAll = async () => {
    if (!window.confirm("Delete all sessions? This cannot be undone.")) return;
    try {
      await axios.delete(`${API}/sessions`);
      setSessions([]);
    } catch(e) {}
  };

  const handleLogoHover = async () => {
    setSidebarOpen(true);
    try {
      const res = await axios.get(`${API}/sessions`);
      setSessions(res.data.sessions || []);
    } catch(e) {}
  };

  return (
    <>
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "20px 48px",
        background: "rgba(10,10,15,0.92)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid #1a1a28",
        zIndex: 100
      }}>
        <div onMouseEnter={handleLogoHover} style={{ display: "inline-block" }}>
          <img
            src="/soochi-logo.png" alt="soochi"
            style={{ height: "32px", cursor: "pointer", mixBlendMode: "screen" }}
            onClick={() => setPage("Upload")}
          />
        </div>
        <div style={{ display: "flex", gap: "32px" }}>
          <button onClick={() => setPage("Landing")} style={{
            background: "none", border: "none", cursor: "pointer",
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "11px", letterSpacing: "0.15em",
            textTransform: "uppercase",
            color: page === "Landing" ? "#4a9eff" : "#555",
            transition: "color 0.2s", padding: 0
          }}>Home</button>
          {NAV.map(n => (
            <button key={n} onClick={() => setPage(n)} style={{
              background: "none", border: "none", cursor: "pointer",
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: "11px", letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: page === n ? "#4a9eff" : "#555",
              transition: "color 0.2s",
              padding: 0
            }}>{n}</button>
          ))}
        </div>
      </nav>

      <div
        onMouseLeave={() => setSidebarOpen(false)}
        style={{
          position: "fixed", top: 0, left: 0, bottom: 0,
          width: sidebarOpen ? "320px" : "0px",
          background: "#0d0d14",
          borderRight: sidebarOpen ? "1px solid #1a1a28" : "none",
          zIndex: 99,
          overflow: "hidden",
          transition: "width 0.3s ease",
          paddingTop: "80px"
        }}
      >
        <div style={{ padding: "24px 20px", opacity: sidebarOpen ? 1 : 0, transition: "opacity 0.2s" }}>
          <div style={{ fontSize: "10px", letterSpacing: "0.3em", color: "#4a9eff", textTransform: "uppercase", marginBottom: "20px" }}>
            Session History
          </div>
          {sessions.length === 0 ? (
            <div style={{ fontSize: "12px", color: "#333" }}>No sessions yet</div>
          ) : (
            sessions.map((s, i) => (
              <div
                key={i}
                onClick={() => { onSessionSelect(s); setSidebarOpen(false); }}
                style={{
                  padding: "14px 16px", marginBottom: "8px",
                  background: "#111118", border: "1px solid #1a1a28",
                  borderRadius: "3px", cursor: "pointer", transition: "border-color 0.2s"
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "#4a9eff"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "#1a1a28"}
              >
                <div style={{ fontSize: "13px", color: "#ccc", marginBottom: "4px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {s.dataset_name}
                </div>
                <div style={{ fontSize: "11px", color: "#444" }}>
                  {s.total_rows?.toLocaleString()} rows · {s.total_columns} vars
                </div>
                <div style={{ fontSize: "10px", color: "#333", marginTop: "4px" }}>
                  {new Date(s.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}

          <div style={{ borderTop: "1px solid #1a1a28", marginTop: "20px", paddingTop: "20px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <button
              onClick={() => { setPage("Logs"); setSidebarOpen(false); }}
              style={{
                background: "#111118", border: "1px solid #222230", color: "#888",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
                padding: "8px 12px", borderRadius: "3px", cursor: "pointer",
                textAlign: "left", letterSpacing: "0.1em"
              }}
            >
              ⚙ Pipeline Logs
            </button>
            <button
              onClick={handleDeleteAll}
              style={{
                background: "#1a0a0a", border: "1px solid #3a1a1a", color: "#ff4a4a",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
                padding: "8px 12px", borderRadius: "3px", cursor: "pointer",
                textAlign: "left", letterSpacing: "0.1em"
              }}
            >
              ✕ Delete All Sessions
            </button>
          </div>
        </div>
      </div>

      {sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 98 }} />
      )}
    </>
  );
}

function LandingPage({ onEnter }) {
  const [phase, setPhase] = React.useState("loading");
  const [visibleVars, setVisibleVars] = React.useState(0);

  const demoVars = [
    { name: "stroke", type: "Binary", codes: [{ code: "0", label: "No Stroke" }, { code: "1", label: "Stroke" }] },
    { name: "age", type: "Continuous", range: "0.08 – 82.0" },
    { name: "bmi", type: "Continuous", range: "10.3 – 97.6" },
    { name: "smoking_status", type: "Categorical Nominal", codes: [{ code: "0", label: "Never Smoked" }, { code: "1", label: "Formerly Smoked" }, { code: "2", label: "Smokes" }] },
    { name: "hypertension", type: "Binary", codes: [{ code: "0", label: "No Hypertension" }, { code: "1", label: "Hypertension" }] },
  ];

  React.useEffect(() => {
    const t = setTimeout(() => setPhase("results"), 3500);
    return () => clearTimeout(t);
  }, []);

  React.useEffect(() => {
    if (phase !== "results" || visibleVars >= demoVars.length) return;
    const t = setTimeout(() => setVisibleVars(v => v + 1), 600);
    return () => clearTimeout(t);
  }, [phase, visibleVars]);

  return (
    <div style={{
      minHeight: "100vh", display: "grid", gridTemplateColumns: "1fr 1fr",
      background: "#0a0a0f", fontFamily: "'IBM Plex Mono', monospace"
    }}>
      <div style={{
        display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "80px 64px", borderRight: "1px solid #1a1a28"
      }}>
        <img src="/soochi-logo.png" alt="soochi"
          style={{ height: "120px", width: "auto", mixBlendMode: "screen", marginBottom: "40px", objectFit: "contain" }} />
        <h1 style={{
          fontSize: "42px", fontWeight: "700", color: "#fff",
          lineHeight: "1.2", letterSpacing: "-1.5px", marginBottom: "20px"
        }}>
          Understand your data<br />before you analyze it.
        </h1>
        <p style={{ fontSize: "14px", color: "#555", lineHeight: "1.8", marginBottom: "48px", maxWidth: "400px" }}>
          Most datasets aren't ready for analysis. Soochi fixes that — automatically identifying variables, standardizing coding, and generating a complete data dictionary in under seven minutes.
        </p>
        <button onClick={onEnter} style={{
          width: "fit-content", padding: "14px 40px",
          background: "#fff", color: "#0a0a0f",
          border: "none", borderRadius: "3px",
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: "13px", fontWeight: "700",
          letterSpacing: "0.1em", textTransform: "uppercase",
          cursor: "pointer", marginBottom: "20px"
        }}>
          Get Started →
        </button>
        <div style={{ fontSize: "9px", letterSpacing: "0.25em", color: "#222", textTransform: "uppercase" }}>
          Structure · Observation · Organization · Classification · Human Inference
        </div>
      </div>

      <div style={{
        background: "#07070d", display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center", padding: "80px 48px", overflow: "hidden"
      }}>
        {phase === "loading" ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: "48px", height: "48px", border: "2px solid #222", borderTop: "2px solid #4a9eff", borderRadius: "50%", animation: "spin 1s linear infinite", marginBottom: "28px" }} />
            <div style={{ fontSize: "13px", color: "#4a9eff", letterSpacing: "0.05em", marginBottom: "8px" }}>Running pipeline — Scout, Interpreter, Writer...</div>
            <div style={{ fontSize: "11px", color: "#444" }}>This takes 2–4 minutes for large datasets</div>
          </div>
        ) : (
          <div style={{ width: "100%" }}>
            <div style={{ fontSize: "10px", letterSpacing: "0.3em", color: "#333", textTransform: "uppercase", marginBottom: "16px" }}>
              Live Preview — healthcare-dataset-stroke-data.xlsx
            </div>
            <div style={{ fontSize: "11px", color: "#4caf50", marginBottom: "20px" }}>
              ✓ 5,110 rows · 12 variables · processing complete
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {demoVars.slice(0, visibleVars).map((v, i) => (
                <div key={i} style={{
                  background: "#111118", border: "1px solid #1a1a28",
                  borderRadius: "3px", padding: "16px 20px",
                  animation: "fadeIn 0.4s ease"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: v.codes ? "10px" : "0" }}>
                    <span style={{ fontSize: "13px", fontWeight: "600", color: "#e8e8e8" }}>{v.name}</span>
                    <span style={{
                      fontSize: "9px", letterSpacing: "0.15em", textTransform: "uppercase",
                      color: "#4a9eff", background: "#0d1a2e", padding: "3px 8px", borderRadius: "2px"
                    }}>{v.type}</span>
                  </div>
                  {v.codes && (
                    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                      {v.codes.map((c, j) => (
                        <span key={j} style={{ fontSize: "11px", color: "#555" }}>
                          <span style={{ color: "#4a9eff" }}>{c.code}</span> = {c.label}
                        </span>
                      ))}
                    </div>
                  )}
                  {v.range && (
                    <div style={{ fontSize: "11px", color: "#555" }}>Range: <span style={{ color: "#aaa" }}>{v.range}</span></div>
                  )}
                </div>
              ))}
              {visibleVars < demoVars.length && (
                <div style={{ display: "flex", gap: "6px", alignItems: "center", padding: "8px 0" }}>
                  <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#4a9eff", animation: "pulse 1s infinite" }} />
                  <span style={{ fontSize: "11px", color: "#333" }}>Analyzing variables...</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

function EntryCard({ entry }) {
  return (
    <div style={{
      background: "#111118", border: "1px solid #222230",
      borderRadius: "4px", padding: "24px", marginBottom: "16px"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
        <div style={{ fontSize: "16px", fontWeight: "600", color: "#fff" }}>{entry.column_name}</div>
        <div style={{
          fontSize: "10px", letterSpacing: "0.15em", textTransform: "uppercase",
          color: "#4a9eff", background: "#0d1a2e", padding: "4px 10px", borderRadius: "2px"
        }}>{entry.variable_type}</div>
      </div>
      {entry.description && (
        <div style={{ fontSize: "13px", color: "#888", lineHeight: "1.6", marginBottom: "12px" }}>
          {entry.description}
        </div>
      )}
      {entry.coding_table && entry.coding_table.length > 0 && (
        <div style={{ marginTop: "12px" }}>
          <div style={{ fontSize: "10px", letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: "8px" }}>Coding Table</div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", color: "#555", padding: "4px 8px", borderBottom: "1px solid #222" }}>Code</th>
                <th style={{ textAlign: "left", color: "#555", padding: "4px 8px", borderBottom: "1px solid #222" }}>Label</th>
              </tr>
            </thead>
            <tbody>
              {entry.coding_table.map((row, i) => (
                <tr key={i}>
                  <td style={{ padding: "4px 8px", color: "#4a9eff", borderBottom: "1px solid #1a1a28" }}>{row.code}</td>
                  <td style={{ padding: "4px 8px", color: "#aaa", borderBottom: "1px solid #1a1a28" }}>{row.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {entry.range && entry.range !== "None" && (
        <div style={{ marginTop: "12px", fontSize: "12px", color: "#666" }}>
          Range: <span style={{ color: "#aaa" }}>{entry.range}</span>
        </div>
      )}
    </div>
  );
}

function LogsPage({ setPage }) {
  const [sessions, setSessions] = React.useState([]);
  const [selectedSession, setSelectedSession] = React.useState(null);
  const [logs, setLogs] = React.useState([]);
  const [loadingLogs, setLoadingLogs] = React.useState(false);

  React.useEffect(() => {
    axios.get(`${API}/sessions`)
      .then(res => setSessions(res.data.sessions || []))
      .catch(() => {});
  }, []);

  const loadLogs = async (session) => {
    setSelectedSession(session);
    setLoadingLogs(true);
    try {
      const res = await axios.get(`${API}/session/${session.id}/logs`);
      setLogs(res.data.logs || []);
    } catch(e) { setLogs([]); }
    setLoadingLogs(false);
  };

  const levelColor = (level) => {
    if (level === "error") return "#ff4a4a";
    if (level === "warn") return "#ffaa4a";
    if (level === "success") return "#4caf50";
    return "#666";
  };

  return (
    <div style={{ padding: "120px 48px 60px", maxWidth: "1100px", margin: "0 auto" }}>
      <div style={{ fontSize: "11px", letterSpacing: "0.3em", color: "#4a9eff", textTransform: "uppercase", marginBottom: "24px" }}>Dev Console</div>
      <h1 style={{ fontSize: "32px", fontWeight: "700", color: "#fff", marginBottom: "40px", letterSpacing: "-1px" }}>Pipeline Logs</h1>
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "24px" }}>
        <div>
          <div style={{ fontSize: "10px", letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: "12px" }}>Sessions</div>
          {sessions.length === 0 ? (
            <div style={{ fontSize: "12px", color: "#333" }}>No sessions</div>
          ) : sessions.map((s, i) => (
            <div key={i} onClick={() => loadLogs(s)} style={{
              padding: "12px 14px", marginBottom: "6px",
              background: selectedSession?.id === s.id ? "#0d1a2e" : "#111118",
              border: selectedSession?.id === s.id ? "1px solid #4a9eff" : "1px solid #1a1a28",
              borderRadius: "3px", cursor: "pointer"
            }}>
              <div style={{ fontSize: "12px", color: "#ccc", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.dataset_name}</div>
              <div style={{ fontSize: "10px", color: "#444", marginTop: "3px" }}>{new Date(s.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
        <div style={{ background: "#050508", border: "1px solid #1a1a28", borderRadius: "4px", padding: "20px", minHeight: "400px" }}>
          {!selectedSession ? (
            <div style={{ fontSize: "12px", color: "#333" }}>← Select a session to view logs</div>
          ) : loadingLogs ? (
            <div style={{ fontSize: "12px", color: "#555" }}>Loading...</div>
          ) : logs.length === 0 ? (
            <div style={{ fontSize: "12px", color: "#333" }}>No logs for this session yet.<br/><br/>
              <span style={{ color: "#555" }}>Logs are written during pipeline execution. Re-run analysis to generate logs.</span>
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} style={{ marginBottom: "6px", fontSize: "11px", display: "flex", gap: "12px" }}>
                <span style={{ color: "#333", flexShrink: 0 }}>{new Date(log.created_at).toLocaleTimeString()}</span>
                <span style={{ color: "#4a9eff", flexShrink: 0, minWidth: "120px" }}>[{log.stage}]</span>
                <span style={{ color: levelColor(log.level) }}>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
      <button onClick={() => setPage("Upload")} style={{
        marginTop: "32px", padding: "10px 20px",
        background: "transparent", color: "#555",
        border: "1px solid #222", borderRadius: "3px",
        fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px", cursor: "pointer"
      }}>← Back</button>
    </div>
  );
}

function DownloadBar({ sessionId, datasetName }) {
  const [selected, setSelected] = React.useState("word");
  const options = [
    { value: "word", label: "Word Report (.docx)" },
    { value: "excel", label: "Recoded Dataset (.xlsx)" },
    { value: "zip", label: "Download All (.zip)" },
  ];
  const handleDownload = () => {
    window.location.href = `${API}/download/${sessionId}/${selected}`;
  };
  return (
    <div style={{ display: "flex", gap: "12px", marginBottom: "32px", alignItems: "center" }}>
      <select value={selected} onChange={e => setSelected(e.target.value)} style={{
        background: "#111118", border: "1px solid #222230", color: "#ccc",
        fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px",
        padding: "10px 14px", borderRadius: "3px", cursor: "pointer", flex: 1
      }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <button onClick={handleDownload} style={{
        padding: "10px 24px", background: "#4a9eff", color: "#000",
        border: "none", borderRadius: "3px",
        fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px",
        fontWeight: "600", cursor: "pointer", letterSpacing: "0.1em",
        textTransform: "uppercase", whiteSpace: "nowrap"
      }}>
        Download →
      </button>
    </div>
  );
}

function ResultsPage({ session, onBack, setPage }) {
  const [entries, setEntries] = useState(null);
  const [loading, setLoading] = useState(true);

  useState(() => {
    axios.get(`${API}/session/${session.session_id}`)
      .then(res => { setEntries(res.data.entries); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: "120px 48px 60px", maxWidth: "860px", margin: "0 auto" }}>
      <div style={{ marginBottom: "32px" }}>
        <div style={{ fontSize: "11px", letterSpacing: "0.2em", color: "#4caf50", textTransform: "uppercase", marginBottom: "8px" }}>
          ✓ Processed Successfully
        </div>
        <div style={{ fontSize: "28px", fontWeight: "700", color: "#fff", marginBottom: "4px" }}>
          {session.dataset_name}
        </div>
        <div style={{ fontSize: "12px", color: "#555", marginBottom: "16px" }}>
          {session.total_rows?.toLocaleString()} rows · {session.total_columns} variables · {session.total_variables} dictionary entries
        </div>
        <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
          <div style={{ fontSize: "11px", color: "#4caf50" }}>✓ Variable types identified</div>
          <div style={{ fontSize: "11px", color: "#4caf50" }}>✓ Coding standardized</div>
          <div style={{ fontSize: "11px", color: "#4caf50" }}>✓ Normality tested</div>
          <button onClick={() => setPage("Logs")} style={{
            fontSize: "11px", color: "#4a9eff", background: "none", border: "none",
            cursor: "pointer", padding: 0, textDecoration: "underline",
            fontFamily: "'IBM Plex Mono', monospace"
          }}>View Processing Logs →</button>
        </div>
      </div>

      <div style={{ background: "#0d0d14", border: "1px solid #1a1a28", borderRadius: "4px", padding: "20px 24px", marginBottom: "24px" }}>
        <div style={{ fontSize: "10px", letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: "12px" }}>How This Was Generated</div>
        <div style={{ display: "flex", gap: "32px", flexWrap: "wrap" }}>
          <div style={{ fontSize: "12px", color: "#666" }}>⬡ Deterministic structure detection</div>
          <div style={{ fontSize: "12px", color: "#666" }}>⬡ Automated coding standardization</div>
          <div style={{ fontSize: "12px", color: "#666" }}>⬡ Inference-based interpretation</div>
        </div>
      </div>

      <DownloadBar sessionId={session.session_id} datasetName={session.dataset_name} />

      {loading ? (
        <div style={{ textAlign: "center", padding: "60px" }}>
          <div style={{ width: "32px", height: "32px", border: "2px solid #222", borderTop: "2px solid #4a9eff", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto" }} />
        </div>
      ) : (
        <div>{entries && entries.map((entry, i) => <EntryCard key={i} entry={entry} />)}</div>
      )}

      <button onClick={onBack} style={{
        marginTop: "32px", padding: "12px 24px",
        background: "transparent", color: "#555",
        border: "1px solid #222", borderRadius: "3px",
        fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px", cursor: "pointer"
      }}>← Analyse another dataset</button>
    </div>
  );
}

function UploadPage({ onComplete, setPage }) {
  const [file, setFile] = useState(null);
  const [userContext, setUserContext] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");

  const handleSubmit = async () => {
    if (!file) return;
    setStatus("uploading");
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("user_context", userContext);
      setProgress("Uploading dataset...");
      const uploadRes = await axios.post(`${API}/upload`, formData);
      const { session_id, total_rows, total_columns, dataset_name, file_path } = uploadRes.data;
      setStatus("analyzing");
      setProgress("Running pipeline — Scout, Interpreter, Writer...");
      const analyzeRes = await axios.post(`${API}/analyze`, {
        session_id, file_path, filename: file.name, user_context: userContext
      });
      onComplete({ session_id, total_rows, total_columns, dataset_name, ...analyzeRes.data });
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(typeof detail === "string" ? detail : JSON.stringify(detail) || e.message || "Something went wrong");
      setStatus("error");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: "120px 20px 60px" }}>
      <div style={{ textAlign: "center", marginBottom: "60px" }}>
        <div style={{ fontSize: "22px", fontWeight: "600", color: "#fff", marginBottom: "12px", letterSpacing: "-0.5px" }}>
          Understand your data before you analyze it.
        </div>
        <img src="/soochi-logo.png" alt="soochi"
          onClick={() => setPage("Logs")}
          style={{ height: "120px", mixBlendMode: "screen", display: "block", margin: "12px auto 8px", cursor: "pointer", width: "auto", objectFit: "contain" }} />
        <div style={{ fontSize: "13px", color: "#888", textAlign: "center", marginBottom: "4px" }}>make your data make sense</div>
        <div style={{ fontSize: "12px", color: "#555", textAlign: "center", marginBottom: "4px" }}>Upload a dataset. Get a clean, structured data dictionary.</div>
        <div style={{ fontSize: "9px", letterSpacing: "0.25em", color: "#333", textAlign: "center", textTransform: "uppercase", marginTop: "8px" }}>
          Structure · Observation · Organization · Classification · Human Inference
        </div>
      </div>

      {status === "idle" && (
        <div style={{ width: "100%", maxWidth: "560px", background: "#111118", border: "1px solid #222230", borderRadius: "4px", padding: "40px" }}>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ fontSize: "11px", letterSpacing: "0.2em", color: "#888", textTransform: "uppercase", display: "block", marginBottom: "8px" }}>Dataset</label>
            <div style={{ border: "1px dashed #333", borderRadius: "3px", padding: "32px", textAlign: "center", cursor: "pointer", background: file ? "#0d1a2e" : "transparent" }}
              onClick={() => document.getElementById("fileInput").click()}>
              {file ? (
                <div>
                  <div style={{ color: "#4a9eff", fontSize: "14px" }}>{file.name}</div>
                  <div style={{ color: "#555", fontSize: "12px", marginTop: "4px" }}>{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
              ) : (
                <div>
                  <div style={{ color: "#555", fontSize: "13px" }}>Drop .xlsx or .sav file</div>
                  <div style={{ color: "#333", fontSize: "11px", marginTop: "4px" }}>or click to browse</div>
                </div>
              )}
            </div>
            <input id="fileInput" type="file" accept=".xlsx,.sav" style={{ display: "none" }} onChange={e => setFile(e.target.files[0])} />
          </div>
          <div style={{ marginBottom: "32px" }}>
            <label style={{ fontSize: "11px", letterSpacing: "0.2em", color: "#888", textTransform: "uppercase", display: "block", marginBottom: "8px" }}>Dataset Context (optional)</label>
            <textarea value={userContext} onChange={e => setUserContext(e.target.value)}
              placeholder="e.g. This is a stroke registry dataset from a tertiary care hospital..."
              style={{ width: "100%", height: "80px", background: "#0a0a0f", border: "1px solid #222230", borderRadius: "3px", color: "#ccc", fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px", padding: "12px", resize: "none", boxSizing: "border-box" }} />
          </div>
          <button onClick={handleSubmit} disabled={!file} style={{
            width: "100%", padding: "14px",
            background: file ? "#4a9eff" : "#1a1a2e", color: file ? "#000" : "#333",
            border: "none", borderRadius: "3px", fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "13px", fontWeight: "600", letterSpacing: "0.1em",
            cursor: file ? "pointer" : "not-allowed", textTransform: "uppercase"
          }}>
            Understand Dataset →
          </button>
        </div>
      )}

      {(status === "uploading" || status === "analyzing") && (
        <div style={{ textAlign: "center" }}>
          <div style={{ width: "48px", height: "48px", border: "2px solid #222", borderTop: "2px solid #4a9eff", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 32px" }} />
          <div style={{ color: "#4a9eff", fontSize: "13px", letterSpacing: "0.1em" }}>{progress}</div>
          <div style={{ color: "#444", fontSize: "11px", marginTop: "8px" }}>This takes 2–4 minutes for large datasets</div>
        </div>
      )}

      {status === "error" && (
        <div style={{ width: "100%", maxWidth: "560px", background: "#1a0a0a", border: "1px solid #3a1a1a", borderRadius: "4px", padding: "32px", textAlign: "center" }}>
          <div style={{ color: "#ff4a4a", fontSize: "13px", marginBottom: "16px" }}>{error}</div>
          <button onClick={() => setStatus("idle")} style={{ background: "transparent", color: "#555", border: "1px solid #333", borderRadius: "3px", padding: "8px 24px", fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px", cursor: "pointer" }}>Try again</button>
        </div>
      )}
    </div>
  );
}

function AboutPage() {
  return (
    <div style={{ maxWidth: "720px", margin: "0 auto", padding: "140px 40px 80px" }}>
      <div style={{ marginBottom: "48px", paddingBottom: "48px", borderBottom: "1px solid #1a1a28", borderLeft: "3px solid #4a9eff", paddingLeft: "24px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "16px", marginBottom: "6px" }}>
          <div style={{ fontSize: "36px", fontWeight: "700", color: "#fff", letterSpacing: "-1px", fontFamily: "Georgia, serif" }}>
            soo·chi
          </div>
          <div style={{ fontSize: "14px", color: "#555", fontStyle: "italic", fontFamily: "Georgia, serif" }}>
            /ˈsuːtʃi/
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
          <div style={{ fontSize: "12px", color: "#555", fontStyle: "italic" }}>noun</div>
          <div style={{ fontSize: "11px", color: "#333" }}>·</div>
          <div style={{ fontSize: "11px", color: "#333" }}>Hindi · सूची</div>
        </div>
        <div style={{ fontSize: "15px", color: "#aaa", lineHeight: "1.7", marginBottom: "10px", fontFamily: "Georgia, serif" }}>
          list; index; catalogue.
        </div>
        <div style={{ fontSize: "13px", color: "#444", fontStyle: "italic", fontFamily: "Georgia, serif" }}>
          "the researcher attached a soochi to the dataset before submission."
        </div>
      </div>

      <div style={{ fontSize: "11px", letterSpacing: "0.3em", color: "#4a9eff", textTransform: "uppercase", marginBottom: "24px" }}>About</div>
      <h1 style={{ fontSize: "40px", fontWeight: "700", color: "#fff", marginBottom: "48px", lineHeight: "1.2", letterSpacing: "-1px" }}>
        Built for the gap between raw data and real analysis.
      </h1>
      {[
        "Soochi is a data preprocessing system designed to bridge the gap between raw datasets and meaningful analysis.",
        "In most real-world workflows, data is not immediately usable. Researchers, analysts, and teams spend a significant amount of time interpreting datasets—understanding what variables represent, cleaning inconsistent coding, handling missing values, and building data dictionaries before any actual analysis can begin. This process is manual, repetitive, and prone to error.",
        "Soochi automates that layer.",
        "It ingests raw tabular data and produces a structured, interpretable output by identifying variable types, standardizing coding schemes, detecting missingness patterns, inferring relationships between variables, and generating a complete data dictionary.",
        "Rather than replacing analysis, Soochi removes the barrier that comes before it. It allows users to move from raw data to analysis-ready structure with clarity and consistency, reducing time spent on interpretation and increasing reliability across datasets.",
        "Soochi is not built to simplify data. It is built to make it understandable.",
        "Soochi makes analysis possible."
      ].map((p, i) => (
        <p key={i} style={{
          fontSize: i === 2 ? "22px" : i === 6 ? "20px" : "15px",
          fontWeight: i === 2 || i === 6 ? "600" : "400",
          color: i === 2 ? "#4a9eff" : i === 5 || i === 6 ? "#fff" : "#888",
          lineHeight: "1.8", marginBottom: i === 6 ? "0" : "24px",
          fontStyle: i === 2 ? "italic" : "normal",
          marginTop: i === 6 ? "32px" : "0"
        }}>{p}</p>
      ))}
    </div>
  );
}

function SoochiForYouPage() {
  const [activeTab, setActiveTab] = React.useState("capabilities");

  const does = [
    "Identifies variable types — categorical, continuous, binary, identifier, empty",
    "Standardizes inconsistent coding (yes/no, 1/2 → industry-standard 0/1)",
    "Detects missingness patterns — true missing, coded missing, structural gaps",
    "Infers variable relationships and code-definition mappings",
    "Generates complete, audit-ready data dictionaries",
    "Runs normality testing with histograms and Q-Q plots per variable",
    "Produces recoded datasets ready for downstream statistical analysis"
  ];
  const doesnt = [
    "Run statistical models or generate findings",
    "Replace your domain expertise or research judgment",
    "Guarantee perfect interpretation in ambiguous edge cases",
    "Infer context it was never given",
    "Scale to enterprise-grade production (yet)"
  ];

  const byTask = [
    { phase: "Before Publication", items: ["Generate codebooks required by journals (PLOS ONE, BMJ, Lancet)", "Standardize variable names across multi-site studies", "Document data for supplementary materials"] },
    { phase: "Before Data Sharing", items: ["FAIR compliance — Findable, Accessible, Interoperable, Reusable", "OSF, UK Data Archive, ICPSR, Zenodo deposit documentation", "Prepare metadata for open science repositories"] },
    { phase: "Before IRB Submission", items: ["Document variables collected for ethics review", "Patient data anonymization documentation", "Consent form variable alignment"] },
    { phase: "Before Grant Submission", items: ["Data management plan variable documentation", "NIH, Wellcome Trust, UKRI data sharing compliance", "Preliminary codebook for grant reviewers"] },
    { phase: "During Analysis", items: ["Onboard new team members to inherited datasets", "Resolve variable ambiguity mid-analysis", "Cross-study variable harmonization"] },
  ];

  const byUser = [
    { role: "PhD Students", pain: "Inherited a dataset with zero documentation. Thesis due in six months.", value: "Instant codebook. Clean coding. No manual interpretation." },
    { role: "Postdoctoral Researchers", pain: "Three sites, three different variable naming conventions, one deadline.", value: "Harmonize datasets across sites before the first analysis runs." },
    { role: "Principal Investigators", pain: "Journal submission requires a data dictionary. Lab doesn't have one.", value: "Compliant, reproducible documentation in under two minutes." },
    { role: "Biostatisticians", pain: "Received an undocumented dataset from a collaborator. Can't trust it yet.", value: "Pre-analysis audit with normality testing and missingness detection built in." },
    { role: "Research Coordinators", pain: "Clinical trial data with inconsistent coding across sites.", value: "Standardized, submission-ready documentation for regulatory review." },
    { role: "Data Managers", pain: "Legacy datasets with no provenance. Governance audit next quarter.", value: "Rescue and document undocumented data before it becomes a liability." },
    { role: "Pharma & CROs", pain: "FDA/EMA submission requires fully documented dataset variables.", value: "Automated, defensible documentation that scales across trials." },
    { role: "Government & Public Health", pain: "National survey data that needs a public-facing codebook.", value: "Consistent, structured output suitable for public repositories." },
  ];

  const tabs = ["capabilities", "by task", "by user"];

  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "140px 40px 80px" }}>
      <div style={{ fontSize: "11px", letterSpacing: "0.3em", color: "#4a9eff", textTransform: "uppercase", marginBottom: "16px" }}>Soochi For You</div>
      <h1 style={{ fontSize: "40px", fontWeight: "700", color: "#fff", marginBottom: "8px", letterSpacing: "-1px" }}>
        Built for everyone who touches data before it's analyzed.
      </h1>
      <p style={{ fontSize: "15px", color: "#666", marginBottom: "48px", lineHeight: "1.7" }}>
        Most data tools assume your data is already clean, coded, and documented. Soochi handles the part that comes before that.
      </p>

      <div style={{ display: "flex", gap: "4px", marginBottom: "48px", borderBottom: "1px solid #1a1a28" }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setActiveTab(t)} style={{
            background: "none", border: "none", cursor: "pointer",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
            letterSpacing: "0.15em", textTransform: "uppercase",
            color: activeTab === t ? "#4a9eff" : "#444",
            padding: "10px 20px",
            borderBottom: activeTab === t ? "2px solid #4a9eff" : "2px solid transparent",
            marginBottom: "-1px", transition: "all 0.2s"
          }}>{t}</button>
        ))}
      </div>

      {activeTab === "capabilities" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "48px" }}>
          <div>
            <div style={{ fontSize: "11px", letterSpacing: "0.25em", color: "#4caf50", textTransform: "uppercase", marginBottom: "24px" }}>✓ Soochi Handles</div>
            {does.map((item, i) => (
              <div key={i} style={{ display: "flex", gap: "16px", marginBottom: "18px", alignItems: "flex-start" }}>
                <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#4caf50", marginTop: "7px", flexShrink: 0 }} />
                <div style={{ fontSize: "14px", color: "#aaa", lineHeight: "1.6" }}>{item}</div>
              </div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: "11px", letterSpacing: "0.25em", color: "#ff4a4a", textTransform: "uppercase", marginBottom: "24px" }}>✗ Soochi Doesn't</div>
            {doesnt.map((item, i) => (
              <div key={i} style={{ display: "flex", gap: "16px", marginBottom: "18px", alignItems: "flex-start" }}>
                <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#ff4a4a", marginTop: "7px", flexShrink: 0 }} />
                <div style={{ fontSize: "14px", color: "#666", lineHeight: "1.6" }}>{item}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "by task" && (
        <div>
          {byTask.map((group, i) => (
            <div key={i} style={{ marginBottom: "40px" }}>
              <div style={{ fontSize: "12px", color: "#4a9eff", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: "16px" }}>{group.phase}</div>
              {group.items.map((item, j) => (
                <div key={j} style={{ display: "flex", gap: "16px", marginBottom: "10px", alignItems: "flex-start" }}>
                  <div style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#333", marginTop: "8px", flexShrink: 0 }} />
                  <div style={{ fontSize: "14px", color: "#888", lineHeight: "1.6" }}>{item}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {activeTab === "by user" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {byUser.map((u, i) => (
            <div key={i} style={{ background: "#111118", border: "1px solid #1a1a28", borderRadius: "4px", padding: "24px" }}>
              <div style={{ fontSize: "14px", fontWeight: "600", color: "#fff", marginBottom: "10px" }}>{u.role}</div>
              <div style={{ fontSize: "12px", color: "#555", marginBottom: "10px", fontStyle: "italic", lineHeight: "1.5" }}>"{u.pain}"</div>
              <div style={{ fontSize: "12px", color: "#4caf50", lineHeight: "1.5" }}>{u.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("Landing");
  const [completedSession, setCompletedSession] = useState(null);

  const handleComplete = (session) => {
    setCompletedSession(session);
    setPage("Results");
  };

  const handleBack = () => {
    setCompletedSession(null);
    setPage("Upload");
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a0f", color: "#e8e8e8", fontFamily: "'IBM Plex Mono', monospace" }}>
      {page !== "Landing" && (
        <Nav page={page} setPage={setPage}
          onSessionSelect={(s) => {
            setCompletedSession({ session_id: s.id, dataset_name: s.dataset_name, total_rows: s.total_rows, total_columns: s.total_columns, total_variables: s.total_columns });
            setPage("Results");
          }} />
      )}
      {page === "Landing" && <LandingPage onEnter={() => setPage("Upload")} />}
      {page === "Upload" && <UploadPage onComplete={handleComplete} setPage={setPage} />}
      {page === "Results" && completedSession && <ResultsPage session={completedSession} onBack={handleBack} setPage={setPage} />}
      {page === "About" && <AboutPage />}
      {page === "Soochi For You" && <SoochiForYouPage />}
      {page === "Logs" && <LogsPage setPage={setPage} />}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0a0f; }
      `}</style>
    </div>
  );
}
