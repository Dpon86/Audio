import React, { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.js";
import "../../static/CSS/AudioWaveformDisplay.css";

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 8;

const AudioWaveformDisplay = ({
  audioFile,
  regions = [],
  onRegionClick,
  zoom = 1,
  playbackRate = 1,
  onReady,
  cutRegion,
}) => {
  const waveformRef = useRef(null);
  const wavesurfer = useRef(null);
  const [zoomLevel, setZoomLevel] = useState(zoom);
  const [speed, setSpeed] = useState(playbackRate);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (!audioFile) return;

    if (wavesurfer.current) {
      try {
        wavesurfer.current.destroy();
      } catch (e) {
        // ignore
      }
    }

    const fileUrl = URL.createObjectURL(audioFile);

    wavesurfer.current = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#b8c1ec",
      progressColor: "#232946",
      height: 100,
      responsive: true,
      minPxPerSec: 100,
      plugins: [RegionsPlugin.create()],
    });

    wavesurfer.current.load(fileUrl);

    wavesurfer.current.on("ready", () => {
      wavesurfer.current.setPlaybackRate(speed);
      setDuration(wavesurfer.current.getDuration());
      setCurrentTime(0);
      if (onReady) onReady(wavesurfer.current);
    });

    // Listen for time updates
    const updateTime = () => {
      if (wavesurfer.current) {
        setCurrentTime(wavesurfer.current.getCurrentTime());
      }
    };
    wavesurfer.current.on("audioprocess", updateTime);
    wavesurfer.current.on("seek", updateTime);

    // Listen for play/pause
    const playHandler = () => setIsPlaying(true);
    const pauseHandler = () => setIsPlaying(false);
    wavesurfer.current.on("play", playHandler);
    wavesurfer.current.on("pause", pauseHandler);

    return () => {
      if (wavesurfer.current) {
        try {
          wavesurfer.current.destroy();
        } catch (e) {
          // ignore
        }
      }
      URL.revokeObjectURL(fileUrl);
    };
  }, [audioFile]); // <--- Only audioFile

  // Update zoom when zoomLevel changes
  useEffect(() => {
    if (wavesurfer.current && wavesurfer.current.isReady) {
      wavesurfer.current.zoom(100 * zoomLevel);
    }
  }, [zoomLevel]);

  useEffect(() => {
    if (wavesurfer.current && wavesurfer.current.isReady && wavesurfer.current.regions) {
      try {
        wavesurfer.current.regions.clear();
      } catch (e) {}
      regions.forEach((reg, idx) => {
        wavesurfer.current.regions.addRegion({
          id: reg.id || `region-${idx}`,
          start: reg.start,
          end: reg.end,
          color: reg.color || "rgba(0,200,0,0.3)",
          drag: false,
          resize: false,
        });
      });
    }
  }, [regions]);

  // Update speed when it changes
  useEffect(() => {
    if (wavesurfer.current) {
      wavesurfer.current.setPlaybackRate(speed);
    }
  }, [speed]);

  // Zoom slider handler
  const handleZoomSlider = (e) => {
    const value = parseFloat(e.target.value);
    setZoomLevel(value);
  };

  // Speed handler
  const handleSpeed = (rate) => {
    setSpeed(rate);
  };

  const handlePlayPause = () => {
    if (wavesurfer.current) {
      wavesurfer.current.playPause();
    }
  };

  // Format time helper
  const formatTime = (t) => {
    if (isNaN(t)) return "0:00";
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="awfd-container">
      <div className="awfd-time-row">
        <span className="awfd-current-time">{formatTime(currentTime)}</span>
        <span className="awfd-divider">/</span>
        <span className="awfd-duration">{formatTime(duration)}</span>
      </div>
      <div ref={waveformRef} className="awfd-waveform" />
      <div className="awfd-controls-row">
        <button className="awfd-play-btn" onClick={handlePlayPause}>
          {isPlaying ? "⏸" : "▶"}
        </button>
        <div className="awfd-zoom-group">
          <label htmlFor="awfd-zoom-slider">Zoom:</label>
          <input
            id="awfd-zoom-slider"
            className="awfd-zoom-slider"
            type="range"
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.05}
            value={zoomLevel}
            onChange={handleZoomSlider}
          />
          <span className="awfd-zoom-value">{zoomLevel.toFixed(2)}x</span>
        </div>
      </div>
      <div className="awfd-controls-row">
        <span className="awfd-speed-label">Speed:</span>
        {[0.25, 0.5, 1, 1.5, 2, 3, 4].map((rate) => (
          <button
            key={rate}
            className={`awfd-speed-btn${speed === rate ? " awfd-speed-btn-active" : ""}`}
            onClick={() => handleSpeed(rate)}
          >
            {rate}x
          </button>
        ))}
      </div>
    </div>
  );
};

export default AudioWaveformDisplay;