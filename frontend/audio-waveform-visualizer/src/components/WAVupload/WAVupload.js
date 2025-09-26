import React, { useRef } from "react";
import "../../static/CSS/WAVupload.css"; 

const WAVupload = ({ onFileSelected }) => {
  const fileInputRef = useRef();

  // Empirical: 268615 KB ≈ 1200 seconds (20 minutes)
  const SECONDS_PER_KB = 1200 / 268615; // ≈ 0.00447

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const sizeKB = file.size / 1024;
      const estimatedSeconds = Math.round(sizeKB * SECONDS_PER_KB);

      // Pass both file and estimated processing time
      onFileSelected && onFileSelected(file, estimatedSeconds);
    }
  };

  return (
    <div className="WAVupload-container">
      <input
        type="file"
        accept=".wav,audio/wav"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <button
        className="WAVupload-button"
        onClick={() => fileInputRef.current && fileInputRef.current.click()}
      >
        Choose WAV File
      </button>
    </div>
  );
};

export default WAVupload;