import React, { useState, useEffect } from "react";
import AudioWaveformEditor from "../components/AudioWaveformEditor/AudioWaveformEditor";

const EditPage = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [finalRepetitive, setFinalRepetitive] = useState([]);
  const [potentialDelete, setPotentialDelete] = useState([]);
  const [potentialRepetitiveGroups, setPotentialRepetitiveGroups] = useState([]);

  useEffect(() => {
    // Load regions from localStorage
    const final = localStorage.getItem("finalRepetitive");
    const del = localStorage.getItem("potentialDelete");
    const potGroups = localStorage.getItem("potentialRepetitiveGroups");
    if (final) setFinalRepetitive(JSON.parse(final));
    if (del) setPotentialDelete(JSON.parse(del));
    if (potGroups) setPotentialRepetitiveGroups(JSON.parse(potGroups));

    // Fetch audio file as Blob from your backend
    const fileName = localStorage.getItem("audioFileName");
    if (fileName) {
      fetch(`/api/audio/download/${fileName}`)
        .then(res => res.blob())
        .then(blob => {
          const file = new File([blob], fileName, { type: blob.type });
          setAudioFile(file);
        });
    }
  }, []);

  return (
    <div>
      <h2>Audio Editing Page</h2>
      {audioFile && (
        <AudioWaveformEditor
          audioFile={audioFile}
          finalRepetitive={finalRepetitive}
          potentialDelete={potentialDelete}
          potentialRepetitiveGroups={potentialRepetitiveGroups}
          onDeleteRegion={(start, end) => {
            setPotentialDelete(potentialDelete.filter(r => !(r.start === start && r.end === end)));
            localStorage.setItem("potentialDelete", JSON.stringify(
              potentialDelete.filter(r => !(r.start === start && r.end === end))
            ));
          }}
        />
      )}
    </div>
  );
};

export default EditPage;