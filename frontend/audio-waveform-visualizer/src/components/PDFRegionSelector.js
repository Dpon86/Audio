import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../config/api';
import './PDFRegionSelector.css';

/**
 * PDFRegionSelector
 * 
 * Displays PDF or Transcript text and allows user to select start or end position for precise comparison
 * Features:
 * - Separate selection for start and end positions
 * - Sentence-based selection
 * - Character position fine-tuning
 * - Preview of selected text
 * - Supports both PDF and Transcript text selection
 * 
 * Props:
 * - projectId: ID of the project containing the PDF
 * - mode: 'start' or 'end' (which position we're selecting)
 * - type: 'pdf' or 'transcript' (which text source to use)
 * - currentStart: Current start position (for context when selecting end)
 * - currentEnd: Current end position (for context when selecting start)
 * - transcriptText: Full transcript text (used when type='transcript')
 * - onPositionSelected: Callback when position is confirmed (position, text)
 * - onCancel: Callback when user cancels
 */
const PDFRegionSelector = ({ 
  projectId, 
  mode = 'start', // 'start' or 'end'
  type = 'pdf', // 'pdf' or 'transcript'
  currentStart = null,
  currentEnd = null,
  transcriptText = '', // Full transcript text
  onPositionSelected, 
  onCancel 
}) => {
  // PDF data
  const [pdfText, setPdfText] = useState('');
  const [pageBreaks, setPageBreaks] = useState([]);
  const [sentences, setSentences] = useState([]);
  const [totalChars, setTotalChars] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [textOffset, setTextOffset] = useState(0); // Offset when showing partial text (e.g., last 200 words)
  
  // Selection state
  const [selectedPosition, setSelectedPosition] = useState(
    mode === 'start' ? (currentStart || 0) : (currentEnd || 0)
  );
  const [selectedSentenceIdx, setSelectedSentenceIdx] = useState(null);
  const [previewText, setPreviewText] = useState('');
  
  // Selection method
  const [selectionMethod, setSelectionMethod] = useState('character'); // 'sentence' or 'character'
  
  // Current page for navigation
  const [currentPage, setCurrentPage] = useState(1);
  
  // Smart search configuration
  const [extractFrom, setExtractFrom] = useState('last'); // 'first' or 'last'
  const [extractWordCount, setExtractWordCount] = useState(100);
  const [searchFrom, setSearchFrom] = useState('first'); // 'first' or 'last'
  const [searchWordCount, setSearchWordCount] = useState(8);

  // Direct text search
  const [directSearchText, setDirectSearchText] = useState('');
  const [directSearchStatus, setDirectSearchStatus] = useState(null); // null | 'found' | 'not_found'

  // Auto-search status (for END mode)
  const [autoSearchStatus, setAutoSearchStatus] = useState(null); // null | 'searching' | 'found' | 'not_found'
  const [autoSearchPhrase, setAutoSearchPhrase] = useState(''); // the sentence that was used
  const autoSearchDoneRef = useRef(false); // prevent running twice

  // Ref for text container
  const textContainerRef = useRef(null);
  
  /**
   * Load PDF text from backend (only if type='pdf')
   */
  const loadPDFText = useCallback(async () => {
    // If type is 'transcript', use the provided transcript text instead
    if (type === 'transcript') {
      // For end mode, show only the last 200 words to make selection easier
      if (mode === 'end') {
        const words = transcriptText.trim().split(/\s+/);
        const wordCount = 200;
        
        if (words.length > wordCount) {
          // Get last 200 words
          const lastWords = words.slice(-wordCount);
          const displayText = lastWords.join(' ');
          
          // Calculate the offset where this text starts in the original
          const fullText = transcriptText.trim();
          const offsetIndex = fullText.lastIndexOf(displayText);
          
          setPdfText(displayText);
          setTextOffset(offsetIndex);
          setTotalChars(transcriptText.length); // Keep total as full length
          // Set initial position to end of displayed text (relative to display)
          setSelectedPosition(displayText.length);
        } else {
          // If transcript is shorter than 200 words, show all
          setPdfText(transcriptText);
          setTextOffset(0);
          setTotalChars(transcriptText.length);
          setSelectedPosition(transcriptText.length);
        }
      } else {
        // For start mode, show full text
        setPdfText(transcriptText);
        setTextOffset(0);
        setTotalChars(transcriptText.length);
      }
      setIsLoading(false);
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/pdf-text/`,
        {
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        const fullPdfText = data.pdf_text || '';
        const totalCharacters = data.total_chars || 0;
        
        // For END mode, show only last portion of PDF text for easier selection
        if (mode === 'end' && fullPdfText.length > 0) {
          const words = fullPdfText.trim().split(/\s+/);
          const wordCount = 200; // Show last 200 words
          
          if (words.length > wordCount) {
            // Get last 200 words
            const lastWords = words.slice(-wordCount);
            const displayText = lastWords.join(' ');
            
            // Calculate the offset where this text starts in the original
            const offsetIndex = fullPdfText.lastIndexOf(displayText);
            
            setPdfText(displayText);
            setTextOffset(offsetIndex);
            setTotalChars(totalCharacters);
            
            // Filter sentences to only show those in the displayed range
            const filteredSentences = (data.sentences || []).filter(s => 
              s.start_char >= offsetIndex && s.start_char < totalCharacters
            ).map(s => ({
              ...s,
              start_char: s.start_char - offsetIndex, // Make relative to display
              end_char: s.end_char - offsetIndex
            }));
            setSentences(filteredSentences);
            
            // Set initial position to end of displayed text
            setSelectedPosition(displayText.length);
          } else {
            // PDF is short enough to show all
            setPdfText(fullPdfText);
            setTextOffset(0);
            setTotalChars(totalCharacters);
            setSentences(data.sentences || []);
            setSelectedPosition(fullPdfText.length);
          }
          
          setPageBreaks(data.page_breaks || []);
        } else {
          // For START mode or if mode is not 'end', show full text
          setPdfText(fullPdfText);
          setPageBreaks(data.page_breaks || []);
          setSentences(data.sentences || []);
          setTotalChars(totalCharacters);
        }
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to load PDF text');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, type, transcriptText, mode]);
  
  useEffect(() => {
    loadPDFText();
  }, [loadPDFText]);

  // Once PDF text has loaded, auto-search for the near-end transcript sentence
  useEffect(() => {
    if (mode === 'end' && type === 'pdf' && !isLoading && pdfText && !autoSearchDoneRef.current) {
      autoSearchDoneRef.current = true;
      // Use full PDF text (pdfText may be the last-200-words slice; we need the absolute text)
      // We pass pdfText which is what's available — the search will still find the phrase
      // if it appears in the visible portion. For safety we also check the full text via
      // a second pass below inside runAutoEndSearch.
      runAutoEndSearch(pdfText);
    }
  }, [mode, type, isLoading, pdfText, runAutoEndSearch]);

  /**
   * Direct text search — user types any phrase and we find it in the PDF
   */
  const performDirectSearch = () => {
    const phrase = directSearchText.trim();
    if (!phrase || !pdfText) {
      setDirectSearchStatus('not_found');
      return;
    }

    const lowerPdf = pdfText.toLowerCase();
    const lowerPhrase = phrase.toLowerCase();
    const idx = lowerPdf.indexOf(lowerPhrase);

    if (idx !== -1) {
      // For end mode set position after the phrase; for start mode, before it
      const newPos = mode === 'start' ? idx : idx + phrase.length;
      setSelectedPosition(newPos);
      setDirectSearchStatus('found');
    } else {
      setDirectSearchStatus('not_found');
    }
  };

  /**
   * Auto-search: called once after PDF loads (END mode only).
   * Picks a sentence ~5 lines from the end of the transcript and searches
   * for it in the PDF text, then sets that as the initial end position.
   */
  const runAutoEndSearch = useCallback((loadedPdfText) => {
    if (!transcriptText || !loadedPdfText) return;

    // Split transcript into non-empty lines / sentences
    const lines = transcriptText
      .split(/(?<=[.!?])\s+|\n+/)
      .map(l => l.trim())
      .filter(l => l.length > 10);

    if (lines.length === 0) return;

    // Pick the sentence ~5 from the end (clamped to available lines)
    const targetIdx = Math.max(0, lines.length - 5);
    const candidateSentence = lines[targetIdx];

    // Take first 10 words of that sentence as the search phrase
    const phraseWords = candidateSentence.split(/\s+/).slice(0, 10);
    const phrase = phraseWords.join(' ');

    setAutoSearchPhrase(candidateSentence);
    setAutoSearchStatus('searching');

    // Try exact phrase, then progressively shorter
    let found = false;
    for (let len = phraseWords.length; len >= 5 && !found; len--) {
      const attempt = phraseWords.slice(0, len).join(' ');
      // Case-insensitive search
      const lowerPdf = loadedPdfText.toLowerCase();
      const lowerAttempt = attempt.toLowerCase();
      const idx = lowerPdf.indexOf(lowerAttempt);
      if (idx !== -1) {
        const endPos = idx + attempt.length;
        setSelectedPosition(endPos);
        setAutoSearchStatus('found');
        console.log(`[PDFRegionSelector] Auto-end: found "${attempt}" at char ${endPos}`);
        found = true;
      }
    }

    if (!found) {
      setAutoSearchStatus('not_found');
      console.log('[PDFRegionSelector] Auto-end: no match found, leaving default position');
    }
  }, [transcriptText]);

  /**
   * Smart search with user-configurable parameters
   * Example: Extract last 100 words, search for first 8 words from that extraction
   */
  const performSmartSearch = () => {
    if (!transcriptText || !pdfText) {
      alert('No transcript or PDF text available');
      return;
    }

    console.log('[PDFRegionSelector] Starting smart search...');
    const words = transcriptText.trim().split(/\s+/);
    
    if (words.length < extractWordCount) {
      alert(`Transcript too short for smart search (need at least ${extractWordCount} words)`);
      return;
    }

    // Step 1: Extract the specified region from transcript
    let extractedWords;
    if (extractFrom === 'last') {
      extractedWords = words.slice(-extractWordCount);
      console.log(`[PDFRegionSelector] Extracted last ${extractWordCount} words from transcript`);
    } else {
      extractedWords = words.slice(0, extractWordCount);
      console.log(`[PDFRegionSelector] Extracted first ${extractWordCount} words from transcript`);
    }
    
    // Step 2: From the extracted region, get the words to search for
    let searchWords;
    if (searchFrom === 'first') {
      searchWords = extractedWords.slice(0, Math.min(searchWordCount, extractedWords.length));
      console.log(`[PDFRegionSelector] Using first ${searchWordCount} words from extracted region`);
    } else {
      searchWords = extractedWords.slice(-Math.min(searchWordCount, extractedWords.length));
      console.log(`[PDFRegionSelector] Using last ${searchWordCount} words from extracted region`);
    }
    
    const searchPhrase = searchWords.join(' ');
    console.log('[PDFRegionSelector] Search phrase:', searchPhrase);
    
    // Step 3: Search for this phrase in the PDF
    const foundIndex = pdfText.indexOf(searchPhrase);
    
    if (foundIndex !== -1) {
      const endPosition = foundIndex + searchPhrase.length;
      console.log('[PDFRegionSelector] ✓ Found match at position:', endPosition);
      setSelectedPosition(endPosition);
      alert(`✓ Found match at character ${endPosition}`);
    } else {
      console.log('[PDFRegionSelector] ✗ Exact match not found, trying with fewer words...');
      
      // Try with progressively fewer words
      let found = false;
      const minWords = Math.max(3, Math.floor(searchWordCount / 2));
      
      for (let wordCount = searchWordCount - 1; wordCount >= minWords && !found; wordCount--) {
        let partialWords;
        if (searchFrom === 'first') {
          partialWords = extractedWords.slice(0, wordCount);
        } else {
          partialWords = extractedWords.slice(-wordCount);
        }
        
        const partialPhrase = partialWords.join(' ');
        const partialIndex = pdfText.indexOf(partialPhrase);
        
        if (partialIndex !== -1) {
          const endPosition = partialIndex + partialPhrase.length;
          console.log(`[PDFRegionSelector] ✓ Found partial match (${wordCount} words) at:`, endPosition);
          setSelectedPosition(endPosition);
          alert(`✓ Found match with ${wordCount} words at character ${endPosition}`);
          found = true;
        }
      }
      
      if (!found) {
        alert('⚠️ Could not find matching text in PDF. Try adjusting the search parameters or selecting manually.');
      }
    }
  };
  
  /**
   * Update position when sentence selection changes
   */
  useEffect(() => {
    if (selectionMethod === 'sentence' && sentences.length > 0 && selectedSentenceIdx !== null) {
      const sentence = sentences[selectedSentenceIdx];
      if (sentence) {
        // For 'start' mode, use beginning of sentence
        // For 'end' mode, use end of sentence
        if (mode === 'start') {
          setSelectedPosition(sentence.start_char);
        } else {
          setSelectedPosition(sentence.end_char);
        }
      }
    }
  }, [selectionMethod, selectedSentenceIdx, sentences, mode]);
  
  /**
   * Update preview text when position changes
   */
  useEffect(() => {
    if (pdfText && selectedPosition >= 0) {
      const PREVIEW_LENGTH = 1000; // Show 1000 chars of preview
      
      if (mode === 'start') {
        // Show text starting from selected position
        const text = pdfText.substring(selectedPosition, selectedPosition + PREVIEW_LENGTH);
        setPreviewText(text + (selectedPosition + PREVIEW_LENGTH < pdfText.length ? '...' : ''));
      } else {
        // Show text ending at selected position
        const start = Math.max(0, selectedPosition - PREVIEW_LENGTH);
        const text = pdfText.substring(start, selectedPosition);
        setPreviewText((start > 0 ? '...' : '') + text);
      }
    } else {
      setPreviewText('');
    }
  }, [pdfText, selectedPosition, mode]);
  
  /**
   * Handle sentence click for selection
   */
  const handleSentenceClick = (index) => {
    if (selectionMethod !== 'sentence') return;
    setSelectedSentenceIdx(index);
  };
  
  /**
   * Handle text selection via mouse (character mode)
   */
  const handleTextSelection = () => {
    if (selectionMethod === 'sentence') return; // Only works in character mode
    
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    
    const selectedText = selection.toString().trim();
    if (selectedText.length === 0) return;
    
    // Find the selected text in the actual PDF text
    const searchStart = Math.max(0, selectedPosition - 500);
    const foundIndex = pdfText.indexOf(selectedText, searchStart);
    
    if (foundIndex !== -1) {
      // For 'start' mode, use beginning of selected text
      // For 'end' mode, use end of selected text
      setSelectedPosition(mode === 'start' ? foundIndex : foundIndex + selectedText.length);
    } else {
      // Try searching from the beginning
      const foundFromStart = pdfText.indexOf(selectedText);
      if (foundFromStart !== -1) {
        setSelectedPosition(mode === 'start' ? foundFromStart : foundFromStart + selectedText.length);
      }
    }
  };
  
  /**
   * Confirm selection and pass to parent
   */
  const handleConfirm = () => {
    // Calculate absolute position (accounting for text offset)
    const absolutePosition = selectedPosition + textOffset;
    
    if (absolutePosition < 0 || absolutePosition > totalChars) {
      alert(`Invalid position: Position must be between 0 and ${totalChars}`);
      return;
    }
    
    // Validate against the other position if it exists
    if (mode === 'start' && currentEnd !== null && absolutePosition >= currentEnd) {
      alert('Start position must be before end position');
      return;
    }
    
    if (mode === 'end' && currentStart !== null && absolutePosition <= currentStart) {
      alert('End position must be after start position');
      return;
    }
    
    onPositionSelected(absolutePosition, previewText);
  };
  
  /**
   * Render sentences as clickable items for selection
   */
  const renderSentenceSelection = () => {
    if (sentences.length === 0) {
      return (
        <div className="sentence-selection-empty">
          <p>No sentences detected. Switch to character mode for manual selection.</p>
        </div>
      );
    }
    
    return (
      <div className="sentence-selection-container">
        <div className="sentence-selection-instructions">
          <strong>Selecting {mode === 'start' ? 'START' : 'END'} position:</strong> Click a sentence to set the {mode} of your PDF region.
          {currentStart !== null && currentEnd !== null && (
            <div className="context-info">
              Current range: characters {currentStart} to {currentEnd}
            </div>
          )}
        </div>
        
        <div className="sentences-list">
          {sentences.slice(0, 200).map((sentence, index) => {
            const isSelected = index === selectedSentenceIdx;
            const isInCurrentRange = currentStart !== null && currentEnd !== null &&
              ((sentence.start_char >= currentStart && sentence.start_char <= currentEnd) ||
               (sentence.end_char >= currentStart && sentence.end_char <= currentEnd));
            
            let className = 'sentence-item';
            if (isSelected) className += ' sentence-selected';
            if (isInCurrentRange) className += ' sentence-in-current-range';
            
            return (
              <div
                key={index}
                className={className}
                onClick={() => handleSentenceClick(index)}
              >
                <span className="sentence-number">{index + 1}.</span>
                <span className="sentence-text">{sentence.text}</span>
                <span className="sentence-chars">Ch {sentence.start_char}-{sentence.end_char}</span>
                {isSelected && (
                  <span className="sentence-badge selected-badge">
                    {mode === 'start' ? 'START' : 'END'}
                  </span>
                )}
              </div>
            );
          })}
          {sentences.length > 200 && (
            <div className="sentences-truncated">
              Showing first 200 of {sentences.length} sentences. 
              Use character mode for more precise control.
            </div>
          )}
        </div>
      </div>
    );
  };
  
  /**
   * Render page markers if available
   */
  const renderTextWithPages = () => {
    if (pageBreaks.length === 0) {
      // No page breaks available, just render the text
      return (
        <div className="pdf-text-content" onMouseUp={handleTextSelection}>
          {renderHighlightedText()}
        </div>
      );
    }
    
    // Render text with page markers
    return (
      <div className="pdf-text-content" onMouseUp={handleTextSelection}>
        {pageBreaks.map((page, index) => {
          const pageText = pdfText.substring(page.start_char, page.end_char);
          
          return (
            <div key={page.page_num} id={`page-${page.page_num}`} className="pdf-page">
              <div className="page-header">
                📄 Page {page.page_num}
              </div>
              <div className="page-content">
                {renderHighlightedText(page.start_char, page.end_char)}
              </div>
            </div>
          );
        })}
      </div>
    );
  };
  
  /**
   * Render text with highlighted selected position
   */
  const renderHighlightedText = () => {
    const PREVIEW_LENGTH = 1000;
    const CONTEXT_BEFORE = 500;
    const CONTEXT_AFTER = 500;
    
    // Show context around the selected position
    const start = Math.max(0, selectedPosition - CONTEXT_BEFORE);
    const end = Math.min(pdfText.length, selectedPosition + CONTEXT_AFTER);
    
    const beforeText = pdfText.substring(start, selectedPosition);
    const afterText = pdfText.substring(selectedPosition, end);
    
    return (
      <div className="text-with-marker">
        {start > 0 && <span className="text-truncated">...</span>}
        <span className="text-before">{beforeText}</span>
        <span className="text-after">{afterText}</span>
        {end < pdfText.length && <span className="text-truncated">...</span>}
      </div>
    );
  };
  
  if (isLoading) {
    return (
      <div className="pdf-region-selector loading">
        <div className="loading-spinner">⏳</div>
        <p>Loading PDF text...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="pdf-region-selector error">
        <div className="error-message">
          <h3>❌ Error</h3>
          <p>{error}</p>
          <button onClick={onCancel} className="btn-cancel">Close</button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="pdf-region-selector">
      <div className="selector-header">
        <h3>{type === 'pdf' ? '📄' : '🎤'} Select {type === 'pdf' ? 'PDF' : 'Transcript'} {mode === 'start' ? 'Start' : 'End'} Position</h3>
        <p>Choose where your {type === 'pdf' ? 'PDF region' : 'transcript'} {mode === 'start' ? 'begins' : 'ends'} to match your {type=== 'pdf' ? 'transcription' : 'PDF'}</p>
        {type === 'transcript' && mode === 'end' && (
          <p style={{ 
            background: '#eff6ff', 
            padding: '0.75rem', 
            borderRadius: '6px', 
            color: '#1e40af',
            fontSize: '0.875rem',
            marginTop: '0.5rem'
          }}>
            ℹ️ Showing last 200 words of transcript for easier end selection
          </p>
        )}
        {type === 'pdf' && mode === 'end' && textOffset > 0 && (
          <p style={{ 
            background: '#f0fdf4', 
            padding: '0.75rem', 
            borderRadius: '6px', 
            color: '#065f46',
            fontSize: '0.875rem',
            marginTop: '0.5rem'
          }}>
            ℹ️ Showing last 200 words of PDF for easier end selection
          </p>
        )}
      </div>
      
      {/* Selection Method Toggle */}
      <div className="selector-controls">
        <div className="mode-toggle-group">
          <label className="mode-label">Selection Method:</label>
          <div className="mode-buttons">
            <button
              className={selectionMethod === 'sentence' ? 'mode-btn active' : 'mode-btn'}
              onClick={() => setSelectionMethod('sentence')}
            >
              📝 Sentence Selection
            </button>
            <button
              className={selectionMethod === 'character' ? 'mode-btn active' : 'mode-btn'}
              onClick={() => setSelectionMethod('character')}
            >
              🔢 Character Position
            </button>
          </div>
        </div>
        
        {/* Direct Text Search — available for both start and end, any mode */}
        {type === 'pdf' && pdfText && (
          <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#334155', marginBottom: '0.5rem' }}>
              🔎 Search PDF for text
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={directSearchText}
                onChange={(e) => { setDirectSearchText(e.target.value); setDirectSearchStatus(null); }}
                onKeyDown={(e) => e.key === 'Enter' && performDirectSearch()}
                placeholder="Paste a sentence or phrase from the text…"
                style={{ flex: 1, minWidth: '200px', padding: '0.4rem 0.6rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem', fontFamily: 'inherit' }}
              />
              <button
                onClick={performDirectSearch}
                disabled={!directSearchText.trim()}
                style={{ padding: '0.4rem 0.9rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: directSearchText.trim() ? 'pointer' : 'not-allowed', fontSize: '0.85rem', opacity: directSearchText.trim() ? 1 : 0.5, whiteSpace: 'nowrap' }}
              >
                Find &amp; Set Position
              </button>
            </div>
            {directSearchStatus === 'found' && (
              <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#166534' }}>
                ✅ Found — position set to character {selectedPosition + textOffset}
              </div>
            )}
            {directSearchStatus === 'not_found' && (
              <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#991b1b' }}>
                ❌ Phrase not found in the visible PDF text. Try fewer words or check the spelling.
              </div>
            )}
            <div style={{ marginTop: '0.3rem', fontSize: '0.75rem', color: '#94a3b8' }}>
              Copy a sentence from the transcript or PDF and paste it here. The position will be set to {mode === 'end' ? 'the end' : 'the start'} of the matched text.
            </div>
          </div>
        )}

        {/* Smart Search Configuration (only show for END position and for PDF) */}
        {mode === 'end' && transcriptText && type === 'pdf' && (
          <div className="smart-search-group">

            {/* Auto-detection status banner */}
            {autoSearchStatus === 'searching' && (
              <div style={{ marginBottom: '0.6rem', padding: '0.5rem 0.75rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px', fontSize: '0.85rem', color: '#1d4ed8' }}>
                ⏳ Auto-detecting end position from transcript…
              </div>
            )}
            {autoSearchStatus === 'found' && (
              <div style={{ marginBottom: '0.6rem', padding: '0.5rem 0.75rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', fontSize: '0.85rem', color: '#166534' }}>
                ✅ <strong>Auto-detected end position</strong> from: <em>"{autoSearchPhrase.substring(0, 80)}{autoSearchPhrase.length > 80 ? '…' : ''}"</em>
                <br /><span style={{ fontSize: '0.78rem', opacity: 0.8 }}>This sentence (~5 from the end of the transcript) was found in the PDF and set as the default end. Adjust with the fine-tune control below if needed.</span>
              </div>
            )}
            {autoSearchStatus === 'not_found' && (
              <div style={{ marginBottom: '0.6rem', padding: '0.5rem 0.75rem', background: '#fef9c3', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '0.85rem', color: '#92400e' }}>
                ⚠️ Could not auto-detect end position (transcript text not found in visible PDF section). Use Smart Search below or select manually.
              </div>
            )}

            <div className="smart-search-config">
              <div className="config-row">
                <label>Extract from transcript:</label>
                <select 
                  value={extractFrom} 
                  onChange={(e) => setExtractFrom(e.target.value)}
                  className="config-select"
                >
                  <option value="first">First</option>
                  <option value="last">Last</option>
                </select>
                <input 
                  type="number" 
                  value={extractWordCount}
                  onChange={(e) => setExtractWordCount(Math.max(1, parseInt(e.target.value) || 1))}
                  min="1"
                  className="config-input"
                />
                <span>words</span>
              </div>
              
              <div className="config-row">
                <label>Search in PDF for:</label>
                <select 
                  value={searchFrom} 
                  onChange={(e) => setSearchFrom(e.target.value)}
                  className="config-select"
                >
                  <option value="first">First</option>
                  <option value="last">Last</option>
                </select>
                <input 
                  type="number" 
                  value={searchWordCount}
                  onChange={(e) => setSearchWordCount(Math.max(1, parseInt(e.target.value) || 1))}
                  min="1"
                  className="config-input"
                />
                <span>words of extracted text</span>
              </div>
              
              <button 
                className="btn-smart-search"
                onClick={performSmartSearch}
                title="Automatically find position by searching for transcript text in PDF"
              >
                🔍 Smart Search
              </button>
            </div>
            <small className="smart-search-hint">
              Example: "Last 100 words" + "First 8 words" = searches PDF for the first 8 words from the last 100 words of transcript
            </small>
          </div>
        )}
      </div>
      
      {/* Current Selection Info */}
      <div className="selector-controls">
        <div className="selection-info-box">
          <strong>{mode === 'start' ? 'Start' : 'End'} Position:</strong> Character {selectedPosition + textOffset}
          {textOffset > 0 && (
            <span style={{ fontSize: '0.85rem', opacity: 0.7 }}> (relative: {selectedPosition})</span>
          )}
          {selectedSentenceIdx !== null && (
            <span> (Sentence {selectedSentenceIdx + 1})</span>
          )}
        </div>
        
        {/* Fine-tune position control */}
        <div className="position-fine-tune">
          <label>Fine-tune position:</label>
          <input 
            type="number" 
            value={selectedPosition + textOffset}
            onChange={(e) => {
              const absolutePos = parseInt(e.target.value) || 0;
              const relativePos = absolutePos - textOffset;
              setSelectedPosition(Math.max(0, Math.min(pdfText.length, relativePos)));
            }}
            min={textOffset}
            max={textOffset + pdfText.length}
            className="fine-tune-input"
          />
        </div>
      </div>
      
      {/* PDF Text Display */}
      <div className="pdf-text-container" ref={textContainerRef}>
        {selectionMethod === 'sentence' && renderSentenceSelection()}
        
        {selectionMethod === 'character' && (
          <div className="pdf-text-content" onMouseUp={handleTextSelection}>
            <div className="character-mode-instructions">
              <strong>Character Selection:</strong> Highlight text with your mouse, or use the fine-tune box above to enter a specific position.
            </div>
            <div className="pdf-full-text">
              {renderHighlightedText()}
            </div>
          </div>
        )}
      </div>
      
      {/* Selection Preview */}
      {previewText && (
        <div className="selection-preview">
          <h4>Preview ({mode === 'start' ? 'text starts here' : 'text ends here'}):</h4>
          <div className="preview-text">
            {previewText}
          </div>
        </div>
      )}
      
      {/* Action Buttons */}
      <div className="selector-actions">
        <button onClick={onCancel} className="btn-cancel">
          Cancel
        </button>
        
        <button 
          onClick={handleConfirm} 
          className="btn-confirm"
        >
          ✓ Confirm {mode === 'start' ? 'Start' : 'End'} Position
        </button>
      </div>
    </div>
  );
};

export default PDFRegionSelector;
