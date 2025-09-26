import React, { useRef, useState } from "react";
import "../../static/CSS/WAVupload.css"; // Reuse your button styles

const PDFUpload = ({ onTaskStarted }) => {
  const fileInputRef = useRef();
  const [uploading, setUploading] = useState(false);

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      setUploading(true);
      const file = e.target.files[0];

      // You may want to collect transcript, segments, words from elsewhere
      // For demo, we'll use dummy values
      const formData = new FormData();
      formData.append("pdf", file);
      formData.append("transcript", localStorage.getItem("transcript") || "");
      formData.append("segments", localStorage.getItem("segments") || "[]");
      formData.append("words", localStorage.getItem("words") || "[]");

      const res = await fetch("/api/analyze-pdf/", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setUploading(false);
      if (data.task_id) {
        onTaskStarted(data.task_id);
      } else {
        alert("Failed to start analysis: " + (data.error || "Unknown error"));
      }
    }
  };

  return (
    <div className="WAVupload-container">
      <input
        type="file"
        accept=".pdf,application/pdf"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <button
        className="WAVupload-button"
        onClick={() => fileInputRef.current && fileInputRef.current.click()}
        disabled={uploading}
      >
        {uploading ? "Uploading..." : "Choose PDF File"}
      </button>
    </div>
  );
};

export default PDFUpload;