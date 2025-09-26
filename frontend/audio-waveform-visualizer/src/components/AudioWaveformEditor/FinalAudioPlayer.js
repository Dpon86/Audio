import React, { useEffect } from "react";
import "./FinalAudioPlayer.css";

const FinalAudioPlayer = ({ audioUrl, originalFileName }) => {
  useEffect(() => {
    console.log("FinalAudioPlayer received audioUrl:", audioUrl);
  }, [audioUrl]);

  const handleDownload = () => {
    if (!audioUrl) return;
    
    // Create a temporary link element
    const downloadLink = document.createElement('a');
    downloadLink.href = audioUrl;
    
    // Generate filename - use original name with "edited_" prefix
    const fileName = originalFileName 
      ? `edited_${originalFileName}` 
      : 'edited_audio.wav';
    
    downloadLink.download = fileName;
    downloadLink.style.display = 'none';
    
    // Append to body, click, and remove
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };

  return (
    <div className="final-audio-container">
      <div className="final-audio-title">Final Audio Preview:</div>
      {audioUrl ? (
        <div className="final-audio-controls">
          <audio 
            controls 
            src={audioUrl} 
            className="final-audio-player"
          />
          <div className="download-button-container">
            <button 
              onClick={handleDownload}
              className="download-button"
            >
              <span className="download-icon"></span>
              Download Edited Audio
            </button>
          </div>
        </div>
      ) : (
        <div className="no-audio-message">
          Process audio to preview and download the edited version.
        </div>
      )}
    </div>
  );
};

export default FinalAudioPlayer;