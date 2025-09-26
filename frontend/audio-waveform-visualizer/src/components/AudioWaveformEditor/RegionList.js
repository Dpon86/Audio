import React from "react";
import "../../static/CSS/RegionList.css";

const RegionList = ({
  regions = [],
  onPlayRegion,
  onToggleRegionType,
  onDeleteAllPotential,
  potentialRepetitiveGroups = [],
}) => {
  // Sort by start time
  const sorted = [...regions].sort((a, b) => a.start - b.start);

  // Add duration to each region
  const regionsWithDuration = sorted.map(r => ({
    ...r,
    duration: r.end - r.start,
  }));

  // Filter and sum durations
  const potentialDeletes = regionsWithDuration.filter(r => r.type === "delete");
  const keeps = regionsWithDuration.filter(r => r.type === "keep");

  const totalDelete = potentialDeletes.reduce((sum, r) => sum + r.duration, 0);
  const totalKeep = keeps.reduce((sum, r) => sum + r.duration, 0);

  // Helper to format seconds as mm:ss
  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="regionlist-container">
      <div className="regionlist-header">
        <strong>Sections:</strong>
        <button
          className="regionlist-deleteall-btn"
          disabled={!potentialDeletes.length}
          onClick={() => {
            if (potentialDeletes.length && onDeleteAllPotential) {
              onDeleteAllPotential(potentialDeletes);
            }
          }}
        >
          Delete All Potential
        </button>
      </div>
      <div style={{ margin: "0.5rem 0" }}>
        <span className="regionlist-delete-label">
          Potential Delete Total: {formatTime(totalDelete)}
        </span>
        {" | "}
        <span className="regionlist-keep-label">
          Keep Total: {formatTime(totalKeep)}
        </span>
      </div>
      <div className="regionlist-scrollbox">
        <ul className="regionlist-ul">
          {regionsWithDuration.map((reg, idx) => (
            <li
              key={idx}
              className={`regionlist-li ${reg.type === "keep" ? "regionlist-keep" : "regionlist-delete"}`}
            >
              <div className="regionlist-info">
                <button
                  className="regionlist-play-btn"
                  onClick={() => onPlayRegion(reg)}
                >
                  ▶
                </button>
                <span>
                  {reg.type === "keep" ? "Keep: " : "Potential Delete: "}
                  {`${reg.start.toFixed(2)}s - ${reg.end.toFixed(2)}s`}
                  {" (" + formatTime(reg.duration) + ")"}
                  {reg.words
                    ? " — " + reg.words.map(w => w.word ?? String(w)).join(" ")
                    : ""}
                </span>
              </div>
              {/* Switch */}
              <div className="regionlist-switch">
                <label className="regionlist-switch-label">
                  <input
                    type="checkbox"
                    checked={reg.type === "keep"}
                    onChange={() => {
                      const newType = reg.type === "keep" ? "delete" : "keep";
                      onToggleRegionType &&
                        onToggleRegionType({ ...reg, type: newType });
                    }}
                  />
                  <span
                    className={`regionlist-slider ${reg.type === "keep" ? "regionlist-slider-keep" : "regionlist-slider-delete"}`}
                  >
                    <span
                      className="regionlist-slider-knob"
                      style={{
                        left: reg.type === "keep" ? "26px" : "2px"
                      }}
                    ></span>
                  </span>
                  <span className={`regionlist-switch-text ${reg.type === "keep" ? "regionlist-keep-label" : "regionlist-delete-label"}`}>
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

export default RegionList;