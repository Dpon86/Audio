import React, { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions";
import "../../static/CSS/WaveformDisplay.css";

const WaveformDisplay = ({ audioFile, segments, repetitiveGroups = [], onSelectRegion }) => {
  const waveformRef = useRef(null);
  const wavesurfer = useRef(null);
  const [selectedRegion, setSelectedRegion] = useState(null);

  // Flatten all repetitive segments for easy lookup
  const allRepetitive = repetitiveGroups.flat();
  
  // Helper: check if a segment is repetitive (original or repeat)
  const isRepetitive = (seg) =>
    repetitiveGroups.some(group =>
      group.length > 1 &&
      group.some(
        rep =>
          Math.abs(rep.start - seg.start) < 0.01 &&
          Math.abs(rep.end - seg.end) < 0.01 &&
          rep.text.trim() === seg.text.trim()
      )
    );

  // Helper: get the group index for a segment
  const getGroupIndex = (seg) =>
    repetitiveGroups.findIndex(group =>
      group.some(
        rep =>
          Math.abs(rep.start - seg.start) < 0.01 &&
          Math.abs(rep.end - seg.end) < 0.01 &&
          rep.text.trim() === seg.text.trim()
      )
    );

  useEffect(() => {
    if (!audioFile) return;

    // Clean up previous instance
    if (wavesurfer.current) {
      wavesurfer.current.destroy();
    }

    // Create new WaveSurfer instance
    wavesurfer.current = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#b8c1ec",
      progressColor: "#232946",
      height: 100,
      responsive: true,
      plugins: [RegionsPlugin.create()]
    });

    // Load audio file
    const fileUrl = URL.createObjectURL(audioFile);
    wavesurfer.current.load(fileUrl);



    // Add regions for all repetitive segments after audio is ready
    wavesurfer.current.on("ready", () => {
      const regionsPlugin = wavesurfer.current.getActivePlugins().regions;
      if (regionsPlugin) {
        regionsPlugin.clearRegions();
        allRepetitive.forEach((seg, idx) => {
          const region = regionsPlugin.addRegion({
            start: seg.start,
            end: seg.end,
            color: "rgba(255,0,0,0.3)", // Red highlight
            drag: false,
            resize: false,
            data: { segIdx: idx }
          });

          // Allow region selection
          region.on("click", () => {
            setSelectedRegion(idx);
            if (onSelectRegion) onSelectRegion(seg, idx);
          });
        });
      }
    });

    // Clean up on unmount
    return () => {
      wavesurfer.current && wavesurfer.current.destroy();
      URL.revokeObjectURL(fileUrl);
    };
  }, [audioFile, repetitiveGroups, onSelectRegion, allRepetitive]);

  useEffect(() => {
    console.log("Segments:", segments);
    console.log("Repetitive groups:", repetitiveGroups);
    console.log("All repetitive:", allRepetitive);
  }, [segments, repetitiveGroups]);


  // Handle transcript click
  const handleTranscriptClick = (seg) => {
    const idx = allRepetitive.findIndex(
      rep =>
        Math.abs(rep.start - seg.start) < 0.01 &&
        Math.abs(rep.end - seg.end) < 0.01 &&
        rep.text.trim() === seg.text.trim()
    );
    if (idx !== -1) {
      setSelectedRegion(idx);
      if (onSelectRegion) onSelectRegion(seg, idx);
      // Optionally, seek to the region in the waveform
      if (wavesurfer.current) {
        wavesurfer.current.seekTo(seg.start / wavesurfer.current.getDuration());
      }
    }
  };

  return (
    <div className="WaveformDisplay-container">
      <div ref={waveformRef} className="WaveformDisplay-waveform" />
      <div className="WaveformDisplay-transcript">
        {segments.map((seg, idx) => {
          const groupIdx = getGroupIndex(seg);
          const isSelected = selectedRegion === groupIdx && groupIdx !== -1;
          return (
            <span
              key={idx}
              className={
                isRepetitive(seg)
                  ? `WaveformDisplay-segment WaveformDisplay-segment-repetitive${isSelected ? " WaveformDisplay-segment-selected" : ""}`
                  : "WaveformDisplay-segment"
              }
              style={isRepetitive(seg) ? { cursor: "pointer", border: "1px solid red" } : {}}
              onClick={() => isRepetitive(seg) && handleTranscriptClick(seg)}
            >
              [{getGroupIndex(seg)}]{seg.text}{" "}
            </span>
          );
        })}
      </div>
    </div>
  );
};

export default WaveformDisplay;