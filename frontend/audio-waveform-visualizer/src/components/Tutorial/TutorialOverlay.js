import React, { useState, useEffect } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';

/* ─────────────────────────────────────────────────────────────
   Exported hook — lets ProjectDetailPageNew manage tutorial state
   so the toggle button can live in the page header.
   ───────────────────────────────────────────────────────────── */
export function useTutorialState() {
  const [tutEnabled, setTutEnabled] = useState(() => {
    const v = localStorage.getItem('audioapp_tutorial');
    if (v === 'enabled')  return true;
    if (v === 'disabled') return false;
    return null; // first visit — show ask dialog
  });

  const enable = () => {
    localStorage.setItem('audioapp_tutorial', 'enabled');
    setTutEnabled(true);
  };
  const disable = () => {
    localStorage.setItem('audioapp_tutorial', 'disabled');
    setTutEnabled(false);
  };

  return { tutEnabled, enable, disable };
}

/* ─────────────────────────────────────────────────────────────
   Tab tutorial content
   ───────────────────────────────────────────────────────────── */
const STEPS = {
  files: [
    {
      title: 'Welcome to Upload & Transcribe',
      body:  'This is your starting point. Upload your audio recording here and the app will automatically convert it to text.',
    },
    {
      title: 'Upload your audio file',
      body:  'Click "Choose Audio File" (or the upload button). Supported formats: MP3, WAV, M4A, FLAC. The file is uploaded to the server.',
    },
    {
      title: 'Start transcription',
      body:  'Once uploaded, click "Start Transcription". This runs an AI speech-to-text process — it takes a few minutes depending on length.',
    },
    {
      title: 'Upload your PDF (optional)',
      body:  'If you have a script PDF, upload it here. This unlocks the PDF Edit tab so you can map chapter markers to audio timestamps.',
    },
    {
      title: 'Wait for completion',
      body:  'Transcription runs in the background. A green tick appears when it is done. Then move on to the Duplicates tab.',
    },
  ],
  duplicates: [
    {
      title: 'What are Duplicates?',
      body:  'When a narrator makes a mistake they often re-read the passage. This tab finds those repeated sections so you can review them and choose which to remove.',
    },
    {
      title: 'Run detection',
      body:  'Click "Start Detection". Choose Multi-Pass mode for the best accuracy. Detection may take a minute or two.',
    },
    {
      title: 'Review the results',
      body:  'Each group shows the duplicate segments with their text. Review each group carefully to confirm they are genuine duplicates before marking them for deletion.',
    },
    {
      title: 'Mark duplicates for deletion',
      body:  'Tick the segments you want to remove. This tab is just for checking — no audio editing happens here. Once you are happy, head to the Edit tab to assemble the clean audio.',
    },
  ],
  pdfedit: [
    {
      title: 'What is PDF Edit?',
      body:  'This tab links your PDF script to positions in the audio. You can mark chapter breaks and set gap durations for the final audiobook.',
    },
    {
      title: 'Load your PDF text',
      body:  'Click "Load PDF Text" at the top of the panel. Your script appears as scrollable text on the left.',
    },
    {
      title: 'Map all to timestamps',
      body:  'Click "Map All to Timestamps". The app scans the text for chapter headings (pink 📖) and paragraph breaks (orange ¶) and maps each to an audio time.',
    },
    {
      title: 'Review the markers',
      body:  'Markers appear as coloured pins in the text. Click any marker to jump to that moment in the audio timeline.',
    },
    {
      title: 'Adjust gap settings',
      body:  'Click a marker to edit it — you can change the gap duration (silence to insert) and whether to use room tone.',
    },
    {
      title: 'Save your markers',
      body:  'Click "Save Markers" when you are happy. These markers are used when assembling the final audio output.',
    },
  ],
  edit: [
    {
      title: 'Welcome to the Audio Editor',
      body:  'This is your main workspace. Use it to mark and remove unwanted sections such as mistakes, retakes, noise, or long pauses.',
    },
    {
      title: 'Navigate the waveform',
      body:  'Click anywhere on the blue waveform to jump to that position. Use the zoom slider (top right of the waveform) to zoom in for precision.',
    },
    {
      title: 'Play and listen',
      body:  'Press Play to listen. The red playhead moves in real time. The text transcript scrolls below the waveform in sync.',
    },
    {
      title: 'Mark a deletion',
      body:  'When you hear a section to remove, click "+ Add Deleted Section". A red region appears at the current playhead position. Drag its edges to adjust.',
    },
    {
      title: 'Align to silence',
      body:  'Click "Align to Silence" to automatically snap all deletion boundaries to the nearest natural pause — this avoids clipped words.',
    },
    {
      title: 'Skip Deleted toggle',
      body:  'Turn on "Skip Deleted" to play back the audio as if the red sections are already removed. Great for checking how the final result will sound.',
    },
    {
      title: 'Save your work',
      body:  'Click "Save Timings" to save your edits. Your work is stored on the server. Then check the Results tab to download the clean audio.',
    },
  ],
  results: [
    {
      title: 'Your processed audio',
      body:  'This tab shows the final assembled audio — your recording with all deleted sections removed and chapter gaps inserted.',
    },
    {
      title: 'Download your file',
      body:  'Click the download button to save the clean audio file to your computer.',
    },
    {
      title: 'Review the stats',
      body:  'See a breakdown of kept vs deleted segment counts and the final running time to check everything looks correct.',
    },
  ],
  review: [
    {
      title: 'Side-by-side comparison',
      body:  'Listen to the original and processed audio at the same time to verify your edits are correct.',
    },
    {
      title: 'Check for clipped words',
      body:  'If a cut sounds abrupt or a word is clipped, go back to the Edit tab and nudge the deletion boundary.',
    },
  ],
  compare: [
    {
      title: 'Text vs script validation',
      body:  'This tab compares the auto-generated audio transcript against your original PDF script to find any discrepancies.',
    },
    {
      title: 'Find differences',
      body:  'Mismatches are highlighted. Use this to spot places where the narrator skipped, added, or changed words.',
    },
    {
      title: 'Decide next steps',
      body:  'Use the comparison report to decide whether any sections need to be re-recorded before final delivery.',
    },
  ],
};

const TAB_NAMES = {
  files:      'Upload & Transcribe',
  duplicates: 'Duplicates',
  pdfedit:    'PDF Edit',
  edit:       'Edit',
  results:    'Results',
  review:     'Review',
  compare:    'Compare PDF',
};

/* ─────────────────────────────────────────────────────────────
   Shared styles
   ───────────────────────────────────────────────────────────── */
const FONT = 'Arial, Helvetica, sans-serif';

const btnBase = {
  fontFamily: FONT,
  border:     'none',
  borderRadius: '7px',
  cursor:     'pointer',
  fontWeight: 600,
  fontSize:   '0.82rem',
  padding:    '7px 16px',
};

/* ─────────────────────────────────────────────────────────────
   Main component — receives state from ProjectDetailPageNew
   ───────────────────────────────────────────────────────────── */
export default function TutorialOverlay({ tutEnabled, onEnable, onDisable }) {
  const { activeTab } = useProjectTab();

  const [step,      setStep]      = useState(0);
  const [minimised, setMinimised] = useState(false);

  // Reset step whenever the user changes tab
  useEffect(() => {
    setStep(0);
    setMinimised(false);
  }, [activeTab]);

  const steps   = STEPS[activeTab] || [];
  const total   = steps.length;
  const current = steps[step] || steps[0];

  /* ── First-visit: ask dialog ─────────────────────────────── */
  if (tutEnabled === null) {
    return (
      <div style={{
        position:       'fixed',
        inset:          0,
        background:     'rgba(15,23,42,0.55)',
        zIndex:         3000,
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'center',
        fontFamily:     FONT,
      }}>
        <div style={{
          background:   '#fff',
          borderRadius: '18px',
          padding:      '36px 40px',
          maxWidth:     '420px',
          width:        '90%',
          boxShadow:    '0 24px 64px rgba(0,0,0,0.25)',
          textAlign:    'center',
        }}>
          <div style={{ fontSize: '3rem', marginBottom: '14px', lineHeight: 1 }}>📖</div>
          <h2 style={{
            margin:     '0 0 10px',
            fontSize:   '1.35rem',
            color:      '#0f172a',
            fontFamily: FONT,
            fontWeight: 700,
          }}>
            Would you like a tutorial?
          </h2>
          <p style={{
            color:      '#64748b',
            margin:     '0 0 28px',
            fontSize:   '0.95rem',
            lineHeight: 1.6,
            fontFamily: FONT,
          }}>
            Step-by-step guidance will appear on each tab to walk you through the whole workflow.
            You can turn it off at any time from the header.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button
              onClick={() => { onEnable(); setStep(0); setMinimised(false); }}
              style={{ ...btnBase, background: '#2563eb', color: '#fff', padding: '11px 32px', fontSize: '1rem' }}
            >
              Yes please
            </button>
            <button
              onClick={onDisable}
              style={{ ...btnBase, background: '#f1f5f9', color: '#475569', border: '1.5px solid #cbd5e1', padding: '11px 32px', fontSize: '1rem' }}
            >
              No thanks
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Tutorial off: nothing to render (toggle is in header) ── */
  if (!tutEnabled) return null;

  /* ── Tutorial on: floating panel ───────────────────────────── */
  return (
    <>

      {/* Minimised restore button */}
      {minimised && (
        <button
          onClick={() => setMinimised(false)}
          style={{
            position:     'fixed',
            bottom:       '24px',
            right:        '24px',
            zIndex:       2500,
            background:   '#1e40af',
            color:        '#fff',
            border:       'none',
            borderRadius: '24px',
            padding:      '10px 20px',
            fontFamily:   FONT,
            fontWeight:   700,
            fontSize:     '0.85rem',
            cursor:       'pointer',
            boxShadow:    '0 4px 18px rgba(0,0,0,0.22)',
            display:      'flex',
            alignItems:   'center',
            gap:          '6px',
          }}
        >
          📖 {TAB_NAMES[activeTab] || 'Tutorial'}
          <span style={{
            background:   '#fff',
            color:        '#1e40af',
            borderRadius: '10px',
            padding:      '1px 7px',
            fontSize:     '0.75rem',
          }}>
            {step + 1}/{total}
          </span>
        </button>
      )}

      {/* Floating tutorial card */}
      {!minimised && total > 0 && (
        <div style={{
          position:     'fixed',
          bottom:       '24px',
          right:        '24px',
          width:        '310px',
          background:   '#fff',
          borderRadius: '16px',
          boxShadow:    '0 8px 36px rgba(0,0,0,0.18)',
          border:       '1px solid #e2e8f0',
          zIndex:       2500,
          fontFamily:   FONT,
          overflow:     'hidden',
        }}>

          {/* Card header */}
          <div style={{
            background:     '#1e40af',
            color:          '#fff',
            padding:        '11px 14px',
            display:        'flex',
            justifyContent: 'space-between',
            alignItems:     'center',
          }}>
            <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>
              📖 {TAB_NAMES[activeTab] || 'Tutorial'}
            </span>
            <button
              onClick={() => setMinimised(true)}
              title="Minimise"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border:     'none',
                color:      '#fff',
                cursor:     'pointer',
                fontFamily: FONT,
                fontSize:   '0.85rem',
                fontWeight: 700,
                borderRadius: '4px',
                padding:    '1px 8px',
                lineHeight:  1.4,
              }}
            >
              –
            </button>
          </div>

          {/* Step progress dots */}
          <div style={{
            display:        'flex',
            gap:            '5px',
            padding:        '11px 16px 0',
            justifyContent: 'center',
          }}>
            {steps.map((_, i) => (
              <div
                key={i}
                onClick={() => setStep(i)}
                title={`Step ${i + 1}`}
                style={{
                  width:        i === step ? '20px' : '8px',
                  height:       '8px',
                  borderRadius: '4px',
                  background:   i === step ? '#2563eb' : (i < step ? '#93c5fd' : '#e2e8f0'),
                  cursor:       'pointer',
                  transition:   'all 0.25s',
                  flexShrink:   0,
                }}
              />
            ))}
          </div>

          {/* Step content */}
          <div style={{ padding: '13px 16px 10px' }}>
            <p style={{
              margin:     '0 0 7px',
              fontWeight: 700,
              fontSize:   '0.93rem',
              color:      '#0f172a',
              fontFamily: FONT,
            }}>
              {step + 1}. {current.title}
            </p>
            <p style={{
              margin:     0,
              fontSize:   '0.84rem',
              color:      '#475569',
              lineHeight: 1.6,
              fontFamily: FONT,
            }}>
              {current.body}
            </p>
          </div>

          {/* Navigation row */}
          <div style={{
            padding:        '6px 16px 14px',
            display:        'flex',
            justifyContent: 'space-between',
            alignItems:     'center',
          }}>
            <button
              onClick={() => setStep(s => Math.max(0, s - 1))}
              disabled={step === 0}
              style={{
                ...btnBase,
                background: step === 0 ? '#f8fafc' : '#f1f5f9',
                color:      step === 0 ? '#94a3b8' : '#334155',
                border:     '1px solid #e2e8f0',
                cursor:     step === 0 ? 'default' : 'pointer',
              }}
            >
              ← Prev
            </button>

            <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontFamily: FONT }}>
              {step + 1} / {total}
            </span>

            {step < total - 1 ? (
              <button
                onClick={() => setStep(s => s + 1)}
                style={{ ...btnBase, background: '#2563eb', color: '#fff' }}
              >
                Next →
              </button>
            ) : (
              <button
                onClick={() => setMinimised(true)}
                style={{ ...btnBase, background: '#16a34a', color: '#fff' }}
              >
                Done ✓
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
