import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import './PDFRegionSelector.css';

/**
 * PDFRegionSelector
 * 
 * Displays PDF text and allows user to select start or end position for precise comparison
 * Features:
 * - Separate selection for start and end positions
 * - Sentence-based selection
 * - Character position fine-tuning
 * - Preview of selected text
 * 
 * Props:
 * - projectId: ID of the project containing the PDF
 * - mode: 'start' or 'end' (which position we're selecting)
 * - currentStart: Current start position (for context when selecting end)
 * - currentEnd: Current end position (for context when selecting start)
 * - onPositionSelected: Callback when position is confirmed (position, text)
 * - onCancel: Callback when user cancels
 */
const PDFRegionSelector = ({ 
  projectId, 
  mode = 'start', // 'start' or 'end'
  currentStart = null,
  currentEnd = null,
  transcriptText = '', // Full transcript text
  onPositionSelected, 
  onCancel 
}) => {
  const { token } = useAuth();
  
  // PDF data
  const [pdfText, setPdfText] = useState('');
  const [pageBreaks, setPageBreaks] = useState([]);
  const [sentences, setSentences] = useState([]);
  const [totalChars, setTotalChars] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Selection state
  const [selectedPosition, setSelectedPosition] = useState(
    mode === 'start' ? (currentStart || 0) : (currentEnd || 0)
  );
  const [selectedSentenceIdx, setSelectedSentenceIdx] = useState(null);
  const [previewText, setPreviewText] = useState('');
  
  // Selection method
  const [selectionMethod, setSelectionMethod] = useState('sentence'); // 'sentence' or 'character'
  
  // Current page for navigation
  const [currentPage, setCurrentPage] = useState(1);
  
  // Smart search configuration
  const [extractFrom, setExtractFrom] = useState('last'); // 'first' or 'last'
  const [extractWordCount, setExtractWordCount] = useState(100);
  const [searchFrom, setSearchFrom] = useState('first'); // 'first' or 'last'
  const [searchWordCount, setSearchWordCount] = useState(8);
  
  // Ref for text container
  const textContainerRef = useRef(null);
  
  /**
   * Load PDF text from backend
   */
  const loadPDFText = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/pdf-text/`,
        {
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setPdfText(data.pdf_text || '');
        setPageBreaks(data.page_breaks || []);
        setSentences(data.sentences || []);
        setTotalChars(data.total_chars || 0);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to load PDF text');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, token]);
  
  useEffect(() => {
    loadPDFText();
  }, [loadPDFText]);
  
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
    if (selectedPosition < 0 || selectedPosition > totalChars) {
      alert(`Invalid position: Position must bebetween 0 and ${totalChars}`);
      return;
    }
    
    // Validate against the other position if it exists
    if (mode === 'start' && currentEnd !== null && selectedPosition >= currentEnd) {
      alert('Start position must be before end position');
      return;
    }
    
    if (mode === 'end' && currentStart !== null && selectedPosition <= currentStart) {
      alert('End position must be after start position');
      return;
    }
    
    onPositionSelected(selectedPosition, previewText);
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
        <h3>📄 Select PDF {mode === 'start' ? 'Start' : 'End'} Position</h3>
        <p>Choose where your PDF region {mode === 'start' ? 'begins' : 'ends'} to match your transcription</p>
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
        
        {/* Smart Search Configuration (only show for END position) */}
        {mode === 'end' && transcriptText && (
          <div className="smart-search-group">
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
          <strong>{mode === 'start' ? 'Start' : 'End'} Position:</strong> Character {selectedPosition}
          {selectedSentenceIdx !== null && (
            <span> (Sentence {selectedSentenceIdx + 1})</span>
          )}
        </div>
        
        {/* Fine-tune position control */}
        <div className="position-fine-tune">
          <label>Fine-tune position:</label>
          <input 
            type="number" 
            value={selectedPosition}
            onChange={(e) => setSelectedPosition(Math.max(0, Math.min(totalChars, parseInt(e.target.value) || 0)))}
            min="0"
            max={totalChars}
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
