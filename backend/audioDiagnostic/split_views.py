"""
Script to split views.py into domain-based modules.
This ensures clean separation of concerns and better maintainability.
"""
import os
import re

# Define the view mappings based on the analysis
VIEW_MAPPINGS = {
    'project_views.py': {
        'classes': [
            ('ProjectListCreateView', 45, 90),
            ('ProjectDetailView', 91, 316),
            ('ProjectTranscriptView', 317, 373),
            ('ProjectStatusView', 537, 584),
            ('ProjectDownloadView', 585, 612),
        ],
        'imports_extra': ["from ..tasks import transcribe_all_project_audio_task, process_project_duplicates_task"]
    },
    'upload_views.py': {
        'classes': [
            ('ProjectUploadPDFView', 374, 403),
            ('ProjectUploadAudioView', 404, 455),
        ],
        'imports_extra': []
    },
    'transcription_views.py': {
        'classes': [
            ('ProjectTranscribeView', 456, 493),
            ('AudioFileListView', 2122, 2153),
            ('AudioFileDetailView', 2154, 2190),
            ('AudioFileTranscribeView', 1918, 1935),
            ('AudioFileRestartView', 1936, 1970),
            ('AudioFileStatusView', 1971, 2040),
            ('AudioTaskStatusWordsView', 1750, 1761),
        ],
        'imports_extra': [
            "from ..tasks import transcribe_all_project_audio_task, transcribe_audio_file_task"
        ]
    },
    'processing_views.py': {
        'classes': [
            ('ProjectProcessView', 494, 536),
            ('AudioFileProcessView', 2041, 2077),
        ],
        'imports_extra': [
            "from ..tasks import process_project_duplicates_task, process_audio_file_task"
        ]
    },
    'duplicate_views.py': {
        'classes': [
            ('ProjectRefinePDFBoundariesView', 1026, 1113),
            ('ProjectDetectDuplicatesView', 1114, 1259),
            ('ProjectDuplicatesReviewView', 1260, 1334),
            ('ProjectConfirmDeletionsView', 1335, 1374),
            ('ProjectVerifyCleanupView', 1375, 1470),
            ('ProjectRedetectDuplicatesView', 1571, 1689),
        ],
        'imports_extra': [
            "from ..tasks import detect_duplicates_task, process_confirmed_deletions_task"
        ]
    },
    'pdf_matching_views.py': {
        'classes': [
            ('ProjectMatchPDFView', 613, 1025),
            ('ProjectValidatePDFView', 1471, 1516),
            ('ProjectValidationProgressView', 1517, 1570),
        ],
        'imports_extra': [
            "from ..tasks import match_pdf_to_audio_task, validate_transcript_against_pdf_task"
        ]
    },
    'infrastructure_views.py': {
        'classes': [
            ('InfrastructureStatusView', 2191, 2225),
            ('TaskStatusView', 2226, 2300),
        ],
        'imports_extra': []
    },
    'legacy_views.py': {
        'functions': [
            ('upload_chunk', 1690, 1704),
            ('assemble_chunks', 1705, 1749),
        ],
        'classes': [
            ('AudioSegmentStatusView', 1762, 1773),
            ('AudiofileDetailView', 1774, 1783),
            ('AudioFileDeleteView', 1797, 1866),
            ('AudiofileUpdateView', 1867, 1891),
            ('ProjectUploadAudioLegacyView', 1892, 1917),
            ('TaskProgressView', 2078, 2121),
        ],
        'imports_extra': [
            "from ..tasks import transcribe_audio_task, transcribe_audio_words_task, analyze_transcription_vs_pdf"
        ]
    },
}

def extract_lines(lines, start, end):
    """Extract lines from the source (1-indexed line numbers)"""
    return lines[start-1:end]

def create_view_file(filename, content_dict, all_lines):
    """Create a view module file"""
    output = []
    
    # Add header
    output.append('"""')
    output.append(f'{filename.replace(".py", "").replace("_", " ").title()} for audioDiagnostic app.')
    output.append('"""')
    output.append('from ._base import *')
    output.append('')
    
    # Add extra imports if needed
    if content_dict.get('imports_extra'):
        for imp in content_dict['imports_extra']:
            output.append(imp)
        output.append('')
    
    # Add classes
    for item in content_dict.get('classes', []):
        class_name, start, end = item
        class_lines = extract_lines(all_lines, start, end)
        output.extend(class_lines)
        output.append('')
    
    # Add functions
    for item in content_dict.get('functions', []):
        func_name, start, end = item
        func_lines = extract_lines(all_lines, start, end)
        output.extend(func_lines)
        output.append('')
    
    return '\n'.join(output)

def main():
    # Read original views.py
    with open('views.py', 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    print(f"Read views.py: {len(lines)} lines")
    
    # Create views directory if it doesn't exist
    os.makedirs('views', exist_ok=True)
    
    # Generate each view module
    for filename, content_dict in VIEW_MAPPINGS.items():
        filepath = os.path.join('views', filename)
        file_content = create_view_file(filename, content_dict, lines)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"Created {filepath}")
    
    print("\n✓ All view modules created successfully!")
    print("\nNext steps:")
    print("1. Review the generated files")
    print("2. Update urls.py imports")
    print("3. Run Django check")
    print("4. Run tests")

if __name__ == '__main__':
    main()
