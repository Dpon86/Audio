/**
 * Client-Side Duplicate Detection Service
 * 
 * Detects duplicate segments within a transcription entirely in the browser.
 * No server processing required - all operations run locally.
 * 
 * Algorithm:
 * 1. Normalize text (lowercase, remove punctuation, trim whitespace)
 * 2. Group segments by normalized text
 * 3. Identify groups with 2+ occurrences as duplicates
 * 4. Mark all but the last occurrence for deletion
 */

class ClientDuplicateDetection {
  constructor() {
    this.lastDetectionResults = null;
  }

  /**
   * Normalize text for comparison
   * Removes punctuation, extra whitespace, and converts to lowercase
   */
  normalizeText(text) {
    if (!text) return '';
    
    // Remove punctuation and special characters
    let normalized = text.replace(/[^\w\s]/g, ' ');
    
    // Convert to lowercase
    normalized = normalized.toLowerCase();
    
    // Collapse multiple spaces into one
    normalized = normalized.replace(/\s+/g, ' ').trim();
    
    return normalized;
  }

  /**
   * Calculate similarity ratio between two strings
   * Simple word-based similarity (Jaccard similarity)
   */
  calculateSimilarity(text1, text2) {
    const words1 = new Set(text1.split(/\s+/).filter(w => w.length > 2));
    const words2 = new Set(text2.split(/\s+/).filter(w => w.length > 2));
    
    if (words1.size === 0 || words2.size === 0) return 0;
    
    const intersection = new Set([...words1].filter(w => words2.has(w)));
    const union = new Set([...words1, ...words2]);
    
    return intersection.size / union.size;
  }

  /**
   * Detect duplicates in a transcription's segments
   * 
   * @param {Array} segments - Array of transcription segments
   *   Each segment should have: { text, start, end } or { text, start_time, end_time }
   * @param {Object} options - Detection options
   *   - minLength: Minimum normalized text length to consider (default: 10 chars)
   *   - minWords: Minimum word count to consider (default: 3 words)
   *   - similarityThreshold: For fuzzy matching (default: 1.0 = exact match only)
   * @param {Function} progressCallback - Optional callback(current, total, status)
   * @returns {Object} Detection results with duplicate groups
   */
  async detectDuplicates(segments, options = {}, progressCallback = null) {
    const {
      minLength = 10,
      minWords = 3,
      similarityThreshold = 1.0, // 1.0 = exact match only, 0.85 = fuzzy matching
    } = options;

    console.log('[ClientDuplicateDetection] Starting detection');
    console.log(`[ClientDuplicateDetection] Segments to analyze: ${segments.length}`);
    console.log(`[ClientDuplicateDetection] Settings:`, { minLength, minWords, similarityThreshold });

    // Track progress
    const reportProgress = (current, total, status) => {
      if (progressCallback) {
        progressCallback(current, total, status);
      }
    };

    reportProgress(0, segments.length, 'Normalizing text...');

    // Step 1: Normalize and prepare segments
    const processedSegments = segments.map((seg, index) => {
      const text = seg.text || '';
      const normalized = this.normalizeText(text);
      const wordCount = normalized.split(/\s+/).filter(w => w.length > 0).length;
      
      return {
        id: seg.id || `seg-${index}`,
        text: text,
        normalized: normalized,
        wordCount: wordCount,
        start_time: seg.start_time ?? seg.start ?? 0,
        end_time: seg.end_time ?? seg.end ?? 0,
        originalIndex: index
      };
    });

    reportProgress(segments.length, segments.length, 'Grouping segments...');

    // Step 2: Group by normalized text (exact matches)
    const textGroups = new Map();
    
    for (let i = 0; i < processedSegments.length; i++) {
      const seg = processedSegments[i];
      
      // Skip if too short or too few words
      if (seg.normalized.length < minLength || seg.wordCount < minWords) {
        continue;
      }

      const key = seg.normalized;
      
      if (!textGroups.has(key)) {
        textGroups.set(key, []);
      }
      
      textGroups.get(key).push(seg);
      
      if (i % 100 === 0) {
        reportProgress(i, processedSegments.length, `Analyzing segment ${i}/${processedSegments.length}...`);
        // Allow UI to update
        await new Promise(resolve => setTimeout(resolve, 0));
      }
    }

    reportProgress(processedSegments.length, processedSegments.length, 'Identifying duplicates...');

    // Step 3: Find groups with 2+ occurrences (duplicates)
    const duplicateGroups = [];
    let groupId = 0;
    let totalDuplicates = 0;

    for (const [normalizedText, occurrences] of textGroups.entries()) {
      if (occurrences.length < 2) {
        // Not a duplicate, only appears once
        continue;
      }

      // Sort by timestamp to identify chronological order
      const sortedOccurrences = occurrences.sort((a, b) => a.start_time - b.start_time);

      // Build segment array with duplicate flags
      const segmentsInGroup = sortedOccurrences.map((seg, idx) => {
        const isLast = (idx === sortedOccurrences.length - 1);
        const isDuplicate = !isLast; // All but last are duplicates
        
        if (isDuplicate) totalDuplicates++;

        return {
          id: seg.id,
          text: seg.text,
          start_time: seg.start_time,
          end_time: seg.end_time,
          normalized_text: normalizedText,
          is_duplicate: isDuplicate, // true = should be deleted
          is_kept: !isDuplicate, // true = should be kept (last occurrence)
          is_last_occurrence: isLast,
          occurrence_number: idx + 1,
          total_occurrences: sortedOccurrences.length
        };
      });

      // Create duplicate group
      duplicateGroups.push({
        group_id: groupId,
        normalized_text: normalizedText,
        original_text: sortedOccurrences[0].text,
        occurrences: sortedOccurrences.length,
        segments: segmentsInGroup,
        first_occurrence_time: sortedOccurrences[0].start_time,
        last_occurrence_time: sortedOccurrences[sortedOccurrences.length - 1].start_time
      });

      groupId++;
    }

    // Sort groups by first occurrence time
    duplicateGroups.sort((a, b) => a.first_occurrence_time - b.first_occurrence_time);

    // Update group IDs after sorting
    duplicateGroups.forEach((group, idx) => {
      group.group_id = idx;
    });

    reportProgress(processedSegments.length, processedSegments.length, 'Complete!');

    const results = {
      total_segments: segments.length,
      analyzed_segments: processedSegments.filter(s => s.normalized.length >= minLength && s.wordCount >= minWords).length,
      duplicate_groups: duplicateGroups,
      total_groups: duplicateGroups.length,
      total_duplicates: totalDuplicates,
      settings: {
        minLength,
        minWords,
        similarityThreshold
      },
      detection_type: 'client-side',
      timestamp: new Date().toISOString()
    };

    this.lastDetectionResults = results;

    console.log('[ClientDuplicateDetection] Detection complete');
    console.log(`[ClientDuplicateDetection] Found ${duplicateGroups.length} duplicate groups`);
    console.log(`[ClientDuplicateDetection] Total duplicate segments: ${totalDuplicates}`);

    return results;
  }

  /**
   * Get last detection results (cached)
   */
  getLastResults() {
    return this.lastDetectionResults;
  }

  /**
   * Clear cached results
   */
  clearResults() {
    this.lastDetectionResults = null;
  }

  /**
   * Export duplicate groups as JSON for download
   */
  exportResults(format = 'json') {
    if (!this.lastDetectionResults) {
      throw new Error('No detection results available');
    }

    if (format === 'json') {
      return JSON.stringify(this.lastDetectionResults, null, 2);
    } else if (format === 'csv') {
      // CSV format: group_id, occurrence_number, text, start_time, end_time, is_duplicate
      let csv = 'Group ID,Occurrence,Text,Start Time,End Time,Is Duplicate\n';
      
      this.lastDetectionResults.duplicate_groups.forEach(group => {
        group.segments.forEach(seg => {
          const escapedText = `"${seg.text.replace(/"/g, '""')}"`;
          csv += `${group.group_id},${seg.occurrence_number},${escapedText},${seg.start_time.toFixed(2)},${seg.end_time.toFixed(2)},${seg.is_duplicate}\n`;
        });
      });
      
      return csv;
    } else {
      throw new Error(`Unsupported export format: ${format}`);
    }
  }

  /**
   * Get statistics about duplicate detection results
   */
  getStatistics() {
    if (!this.lastDetectionResults) {
      return null;
    }

    const results = this.lastDetectionResults;
    const totalTimeInDuplicates = results.duplicate_groups.reduce((sum, group) => {
      return sum + group.segments
        .filter(seg => seg.is_duplicate)
        .reduce((segSum, seg) => segSum + (seg.end_time - seg.start_time), 0);
    }, 0);

    return {
      total_segments: results.total_segments,
      analyzed_segments: results.analyzed_segments,
      duplicate_groups: results.total_groups,
      duplicate_segments: results.total_duplicates,
      kept_segments: results.analyzed_segments - results.total_duplicates,
      duplicate_time_seconds: totalTimeInDuplicates,
      duplicate_time_formatted: this.formatDuration(totalTimeInDuplicates),
      detection_type: results.detection_type,
      timestamp: results.timestamp
    };
  }

  /**
   * Format duration in seconds as MM:SS
   */
  formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
}

// Export singleton instance
const clientDuplicateDetection = new ClientDuplicateDetection();
export default clientDuplicateDetection;
