import React, { useState, useEffect, useRef } from "react";
import WAVupload from "../components/WAVupload/WAVupload";
import WaveformDisplay from "../components/waveformDisplay/WaveformDisplay";
import { useNavigate } from "react-router-dom";
import "../static/CSS/AudioPage.css";

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB

const MOTIVATIONAL_MESSAGES = [
  "Go make a cup of tea ☕",
  "Please leave your computer on, I'll do all the hard work!",
  "I hope you are having a great day, use this time to get up and stretch.",
  "Take a deep breath and relax, your audio is in good hands.",
  "Think of something you're grateful for today.",
  "Maybe check your emails or messages while you wait.",
  "Time for a quick walk or some stretches!",
  "Stay hydrated! Grab a glass of water.",
  "You’re awesome for automating your workflow!",
  "Smile! Good things are coming your way.",
];

function extractRegionsFromRepetitiveGroups(repetitiveGroups) {
  const finalRepetitive = [];
  const potentialDelete = [];
  repetitiveGroups.forEach(group => {
    if (group.length > 1) {
      const sorted = [...group].sort((a, b) => a.start - b.start);
      sorted.slice(0, -1).forEach(item => potentialDelete.push(item));
      finalRepetitive.push(sorted[sorted.length - 1]);
    }
  });
  return { finalRepetitive, potentialDelete };
}

const AudioPage = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [audioDuration, setAudioDuration] = useState(null); // in seconds
  const [segments, setSegments] = useState([]);
  const [repetitiveSegments, setRepetitiveSegments] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [finalRepetitive, setFinalRepetitive] = useState([]);
  const [potentialDelete, setPotentialDelete] = useState([]);
  const [messageIndex, setMessageIndex] = useState(0);
  const [processingStart, setProcessingStart] = useState(null);
  const navigate = useNavigate();
  const [potentialRepetitiveGroups, setPotentialRepetitiveGroups] = useState([]);
  const messageIntervalRef = useRef();

  useEffect(() => {
    const savedFinal = localStorage.getItem("finalRepetitive");
    const savedDelete = localStorage.getItem("potentialDelete");
    if (savedFinal) setFinalRepetitive(JSON.parse(savedFinal));
    if (savedDelete) setPotentialDelete(JSON.parse(savedDelete));
  }, []);

  useEffect(() => {
    if (processing) {
      setProcessingStart(Date.now());
      setMessageIndex(0);
      messageIntervalRef.current = setInterval(() => {
        setMessageIndex((prev) => (prev + 1) % MOTIVATIONAL_MESSAGES.length);
      }, 20000); // Change message every 20 seconds
    } else {
      clearInterval(messageIntervalRef.current);
    }
    return () => clearInterval(messageIntervalRef.current);
  }, [processing]);

  // Estimate processing time: e.g., 1.5x audio duration (tweak as needed)
  const estimatedProcessingTime = audioDuration ? Math.ceil(audioDuration * 1.5) : null;

  // Calculate time left
  let timeLeft = null;
  if (processing && estimatedProcessingTime && processingStart) {
    const elapsed = Math.floor((Date.now() - processingStart) / 1000);
    timeLeft = Math.max(0, estimatedProcessingTime - elapsed);
  }

  async function uploadFileInChunks(file, duration) {
    setProcessing(true);
    setUploadProgress(0);
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const uploadId = Date.now() + '-' + file.name;

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(file.size, start + CHUNK_SIZE);
      const chunk = file.slice(start, end);

      const formData = new FormData();
      formData.append('chunk', chunk);
      formData.append('upload_id', uploadId);
      formData.append('chunk_index', i);
      formData.append('total_chunks', totalChunks);
      formData.append('filename', file.name);

      await fetch('/api/audio/upload-chunk/', {
        method: 'POST',
        body: formData,
      });

      setUploadProgress(Math.round(((i + 1) / totalChunks) * 100));
    }

    // After all chunks are uploaded, notify the backend to assemble and process
    const response = await fetch('/api/audio/assemble-chunks/', {
      method: 'POST',
      body: JSON.stringify({ upload_id: uploadId, filename: file.name }),
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    localStorage.setItem("audioFileName", data.filename);
    const taskId = data.task_id;

    // Poll for result
    const poll = setInterval(async () => {
      const res = await fetch(`/api/audio/status/${taskId}/`);
      if (res.status === 200) {
        const result = await res.json();
        setSegments(result.all_segments || []);
        setRepetitiveSegments(result.repetitive_groups || []);
        setPotentialRepetitiveGroups(result.potential_repetitive_groups || []);
        const { finalRepetitive, potentialDelete } = extractRegionsFromRepetitiveGroups(result.repetitive_groups || []);
        setFinalRepetitive(finalRepetitive);
        setPotentialDelete(potentialDelete);
        localStorage.setItem("finalRepetitive", JSON.stringify(finalRepetitive));
        localStorage.setItem("potentialDelete", JSON.stringify(potentialDelete));
        localStorage.setItem("audioSegments", JSON.stringify(result.all_segments || []));
        localStorage.setItem("potentialRepetitiveGroups", JSON.stringify(result.potential_repetitive_groups || []));
        setProcessing(false);
        setUploadProgress(0);
        clearInterval(poll);
      }
    }, 2000);
  }

  // Accepts duration from WAVupload
  const handleFileSelected = async (file, durationSeconds) => {
    setAudioFile(file);
    setAudioDuration(durationSeconds);
    await uploadFileInChunks(file, durationSeconds);
  };

  return (
    <div className="audiopage-container">
      <WAVupload onFileSelected={handleFileSelected} />
      {processing && (
        <div className="audiopage-processing-box">
          <div className="audiopage-estimate">
            {estimatedProcessingTime && (
              <div>
                <b>
                  It will take approximately {`${Math.floor(estimatedProcessingTime / 60)}:${(estimatedProcessingTime % 60).toString().padStart(2, '0')}`} minutes to process your audio.                  {timeLeft !== null && timeLeft > 0 && (
                    <> 
                      <br />
                      Estimated time left: {`${Math.floor(timeLeft / 60)}:${(timeLeft % 60).toString().padStart(2, '0')} minutes`}
                    </>
                  )}
                </b>
              </div>
            )}
          </div>
            <div className="audiopage-infinity-spinner">
              <svg className="infinity-svg" viewBox="0 0 100 50" width="120" height="60">
                <path
                  className="infinity-path"
                  d="M10,25 Q25,0 50,25 Q75,50 90,25 Q75,0 50,25 Q25,50 10,25"
                  fill="none"
                  stroke="#4fa94d"
                  strokeWidth="8"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          <div className="audiopage-motivation">
            {MOTIVATIONAL_MESSAGES[messageIndex]}
          </div>
        </div>
      )}
      {audioFile && segments.length > 0 && (
        <>
          <WaveformDisplay
            audioFile={audioFile}
            segments={segments}
            repetitiveGroups={repetitiveSegments}
          />
          <button
            className="audiopage-edit-btn"
            disabled={
              !audioFile ||
              !finalRepetitive.length ||
              !potentialDelete.length
            }
            onClick={() => {
              localStorage.setItem("finalRepetitive", JSON.stringify(finalRepetitive));
              localStorage.setItem("potentialDelete", JSON.stringify(potentialDelete));
              localStorage.setItem("audioSegments", JSON.stringify(segments));
              navigate("/EditPage");
            }}
          >
            Pass to Editing Page
          </button>
        </>
      )}
    </div>
  );
};

export default AudioPage;