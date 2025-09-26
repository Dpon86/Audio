import React, { useRef, useState, useEffect } from "react";
import AudioWaveformDisplay from "./AudioWaveformDisplay";
import RegionList from "./RegionList";
import FinalAudioPlayer from "./FinalAudioPlayer";
import NoiseRegionList from "./NoiseRegionList";


const AudioWaveformEditor = ({
  audioFile,
  finalRepetitive = [],
  potentialDelete = [],
  potentialRepetitiveGroups = [],
}) => {

  const wavesurferRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [regions, setRegions] = useState([]);
  const [finalAudioUrl, setFinalAudioUrl] = useState(null);
  const [noiseRegions, setNoiseRegions] = useState([]);
  // 2. Initialize regions from props when they change
  useEffect(() => {
    setRegions([
      ...potentialDelete.map(r => ({ ...r, type: "delete" })),
      ...finalRepetitive.map(r => ({ ...r, type: "keep" })),
    ].sort((a, b) => a.start - b.start));
  }, [finalRepetitive, potentialDelete]);

  // Debug: log regions passed to RegionList
  console.log("AudioWaveformEditor regions:", regions);

  // Play a region from the waveform
  const handlePlayRegion = (reg) => {
    if (wavesurferRef.current) {
      wavesurferRef.current.play(reg.start, reg.end);
    }
  };

  // 3. Toggle region type in state
  const handleToggleRegionType = (updatedRegion) => {
    setRegions(prev =>
      prev.map(r =>
        r.start === updatedRegion.start && r.end === updatedRegion.end
          ? { ...r, type: updatedRegion.type }
          : r
      )
    );
  };

    const handleDeleteAllPotential = async (potentialDeletes) => {
      console.log("Sending to backend:", potentialDeletes);
      const response = await fetch("/api/audio/cut/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fileName: audioFile.name,
          deleteSections: potentialDeletes.map(r => ({
            start: r.start,
            end: r.end
          }))
        })
      });
      console.log("Backend response status:", response.status);
      const contentType = response.headers.get("content-type");
      console.log("Backend response content-type:", contentType);
    
      if (!response.ok) {
        const text = await response.text();
        console.error("Backend error:", text);
        alert("Backend error: " + text);
        return;
      }
    
      if (!contentType.startsWith("audio/")) {
        const text = await response.text();
        console.error("Not an audio file:", text);
        alert("Not an audio file: " + text);
        return;
      }
    
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      console.log("Setting finalAudioUrl:", url);
      setFinalAudioUrl(url);
    };

    return (
      <div>
        <AudioWaveformDisplay
          audioFile={audioFile}
          regions={regions}
          zoom={zoom}
          playbackRate={playbackRate}
          onReady={ws => (wavesurferRef.current = ws)}
        />
        <RegionList
          regions={regions}
          onToggleRegionType={handleToggleRegionType}
          onPlayRegion={handlePlayRegion}
          onDeleteAllPotential={handleDeleteAllPotential}
          potentialRepetitiveGroups={potentialRepetitiveGroups}
        />
        <NoiseRegionList
          noiseRegions={noiseRegions}
          onPlayRegion={handlePlayRegion}
        />
        <FinalAudioPlayer 
          audioUrl={finalAudioUrl} 
          originalFileName={audioFile?.name}
        />
      </div>
    );
  };

export default AudioWaveformEditor;