import React, { useState, useEffect } from "react";
import "../../static/CSS/NoiseRegionList.css";

const NoiseRegionList = ({
  noiseRegions = [],
  onPlayRegion,
  onChange, // optional: callback to parent if you want to sync changes
}) => {
  const [localNoise, setLocalNoise] = useState([]);

  // Debug: log incoming props and local state
  useEffect(() => {
    console.log("NoiseRegionList: received noiseRegions prop:", noiseRegions);
  }, [noiseRegions]);
  useEffect(() => {
    console.log("NoiseRegionList: localNoise state:", localNoise);
  }, [localNoise]);

  // Initialize local state from prop
  useEffect(() => {
    setLocalNoise(
      (noiseRegions || []).map(r => ({
        ...r,
        type: r.type || "delete"
      }))
    );
  }, [noiseRegions]);

  // Optionally notify parent of changes
  useEffect(() => {
    if (onChange) onChange(localNoise);
  }, [localNoise, onChange]);

  const handleToggleRegionType = (updatedRegion) => {
    setLocalNoise(prev =>
      prev.map(r =>
        r.start === updatedRegion.start && r.end === updatedRegion.end
          ? { ...r, type: updatedRegion.type }
          : r
      )
    );
  };

  const handleDeleteAllNoise = () => {
    setLocalNoise(prev =>
      prev.map(r => ({ ...r, type: "delete" }))
    );
  };

  const sorted = [...localNoise].sort((a, b) => a.start - b.start);
  const noiseDeletes = sorted.filter(r => r.type === "delete");

  return (
    <div className="noiseregionlist-container">
      <div className="noiseregionlist-header">
        <strong>Noise Sections:</strong>
        <button
          className="noiseregionlist-deleteall-btn"
          disabled={!noiseDeletes.length}
          onClick={handleDeleteAllNoise}
        >
          Delete All Noise
        </button>
      </div>
      <div className="noiseregionlist-scrollbox">
        <ul className="noiseregionlist-ul">
          {sorted.map((reg, idx) => (
            <li
              key={idx}
              className={`noiseregionlist-li ${reg.type === "keep" ? "noiseregionlist-keep" : "noiseregionlist-delete"}`}
            >
              <div className="noiseregionlist-info">
                <button
                  className="noiseregionlist-play-btn"
                  onClick={() => onPlayRegion && onPlayRegion(reg)}
                >
                  ▶
                </button>
                <span>
                  {reg.type === "keep" ? "Keep: " : "Noise: "}
                  {`${reg.start.toFixed(2)}s - ${reg.end.toFixed(2)}s`}
                </span>
              </div>
              <div className="noiseregionlist-switch">
                <label className="noiseregionlist-switch-label">
                  <input
                    type="checkbox"
                    checked={reg.type === "keep"}
                    onChange={() => {
                      const newType = reg.type === "keep" ? "delete" : "keep";
                      handleToggleRegionType({ ...reg, type: newType });
                    }}
                  />
                  <span
                    className={`noiseregionlist-slider ${reg.type === "keep" ? "noiseregionlist-slider-keep" : "noiseregionlist-slider-delete"}`}
                  >
                    <span
                      className="noiseregionlist-slider-knob"
                      style={{
                        left: reg.type === "keep" ? "26px" : "2px"
                      }}
                    ></span>
                  </span>
                  <span className={`noiseregionlist-switch-text ${reg.type === "keep" ? "noiseregionlist-keep-label" : "noiseregionlist-delete-label"}`}>
                    {reg.type === "keep" ? "Keep" : "Delete"}
                  </span>
                </label>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default NoiseRegionList;