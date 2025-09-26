import React, { useState, useEffect } from "react";
import PDFUpload from "../components/PDFUpload/PDFUpload";

const PDFAnalysisPage = () => {
  const [taskId, setTaskId] = useState(null);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
    console.log("Displaying!")
  // Poll for result if taskId is set
  useEffect(() => {
    if (!taskId) return;
    setStatus("processing");
    const poll = setInterval(async () => {
      const res = await fetch(`/api/celery-status/${taskId}/`);
      if (res.status === 200) {
        const data = await res.json();
        if (data.status === "complete" || data.pdf_section) {
          setResult(data);
          setStatus("done");
          clearInterval(poll);
        }
      }
    }, 2000);
    return () => clearInterval(poll);
  }, [taskId]);

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24, marginTop: "150px" }}>
      <h2>PDF Analysis</h2>
      {!taskId && <PDFUpload onTaskStarted={setTaskId} />}
      {status === "processing" && (
        <div>
          <div className="audiopage-infinity-spinner">
            {/* You can reuse your infinity spinner here */}
            <svg className="infinity-svg" viewBox="0 0 100 50" width="120" height="60">
              <path
                className="infinity-path"
                d="M25,25 C25,10 50,10 50,25 C50,40 75,40 75,25 C75,10 50,10 50,25 C50,40 25,40 25,25"
                fill="none"
                stroke="#4fa94d"
                strokeWidth="10"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div>Analyzing PDF, please wait...</div>
        </div>
      )}
      {status === "done" && result && (
        <div style={{ marginTop: 24 }}>
          <h3>Section of Book Covered:</h3>
          <pre style={{ whiteSpace: "pre-wrap", background: "#f8f8f8", padding: 12 }}>{result.pdf_section}</pre>
          <h3>Missing Words:</h3>
          <div>{result.missing_words && result.missing_words.length ? result.missing_words.join(", ") : "None"}</div>
          <h3>Repeated Sections (to delete):</h3>
          <ul>
            {result.repeated_sections && result.repeated_sections.length
              ? result.repeated_sections.map((r, i) => (
                  <li key={i}>
                    <b>{r.sentence}</b> <br />
                    <span>Start: {r.start}, End: {r.end}</span>
                  </li>
                ))
              : <li>None</li>}
          </ul>
          <h3>Kept Sentences:</h3>
          <ul>
            {result.kept_sentences && result.kept_sentences.length
              ? result.kept_sentences.map((s, i) => (
                  <li key={i}>{s.text}</li>
                ))
              : <li>None</li>}
          </ul>
        </div>
      )}
    </div>
  );
};

export default PDFAnalysisPage;