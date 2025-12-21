"""
Script to split tasks.py into domain-based modules.
This ensures clean separation of concerns and better maintainability.
"""
import os
import re

# Define the task mappings based on analysis
TASK_MAPPINGS = {
    'transcription_tasks.py': {
        'functions': [
            ('ensure_ffmpeg_in_path', 20, 34),
        ],
        'tasks': [
            ('transcribe_all_project_audio_task', 36, 157),
            ('transcribe_audio_file_task', 159, 265),
            ('transcribe_audio_task', 930, 1015),
            ('transcribe_audio_words_task', 1121, 1187),
        ],
        'helpers': [
            ('split_segment_to_sentences', 1017, 1083),
            ('find_noise_regions', 1085, 1119),
        ]
    },
    'duplicate_tasks.py': {
        'tasks': [
            ('process_project_duplicates_task', 267, 427),
            ('detect_duplicates_task', 2039, 2171),
            ('process_confirmed_deletions_task', 1245, 1431),
        ],
        'helpers': [
            ('identify_all_duplicates', 738, 791),
            ('mark_duplicates_for_removal', 793, 837),
            ('detect_duplicates_against_pdf_task', 2173, 2378),
        ]
    },
    'pdf_tasks.py': {
        'tasks': [
            ('match_pdf_to_audio_task', 1543, 1678),
            ('analyze_transcription_vs_pdf', 1189, 1243),
            ('validate_transcript_against_pdf_task', 2380, 2644),
        ],
        'helpers': [
            ('find_pdf_section_match', 567, 596),
            ('find_pdf_section_match_task', 1680, 1939),
            ('identify_pdf_based_duplicates', 598, 646),
            ('find_text_in_pdf', 732, 736),
            ('find_missing_pdf_content', 839, 857),
            ('calculate_comprehensive_similarity_task', 1941, 2003),
            ('extract_chapter_title_task', 2005, 2037),
        ]
    },
    'audio_processing_tasks.py': {
        'tasks': [
            ('process_audio_file_task', 429, 565),
        ],
        'helpers': [
            ('generate_processed_audio', 680, 730),
            ('generate_clean_audio', 1433, 1488),
            ('transcribe_clean_audio_for_verification', 1490, 1541),
            ('assemble_final_audio', 869, 914),
        ]
    },
    'utils.py': {
        'functions': [
            ('save_transcription_to_db', 648, 678),
            ('get_final_transcript_without_duplicates', 859, 867),
            ('get_audio_duration', 916, 923),
            ('normalize', 925, 928),
        ]
    }
}

def extract_lines(lines, start, end):
    """Extract lines from the source (1-indexed line numbers)"""
    return lines[start-1:end]

def create_task_file(filename, content_dict, all_lines):
    """Create a task module file"""
    output = []
    
    # Add header
    output.append('"""')
    output.append(f'{filename.replace(".py", "").replace("_", " ").title()} for audioDiagnostic app.')
    output.append('"""')
    output.append('from ._base import *')
    output.append('')
    
    # Add tasks (Celery tasks)
    for item in content_dict.get('tasks', []):
        task_name, start, end = item
        task_lines = extract_lines(all_lines, start, end)
        output.extend(task_lines)
        output.append('')
    
    # Add helper functions
    for item in content_dict.get('helpers', []):
        func_name, start, end = item
        func_lines = extract_lines(all_lines, start, end)
        output.extend(func_lines)
        output.append('')
    
    # Add regular functions
    for item in content_dict.get('functions', []):
        func_name, start, end = item
        func_lines = extract_lines(all_lines, start, end)
        output.extend(func_lines)
        output.append('')
    
    return '\n'.join(output)

def main():
    # Read original tasks.py
    with open('tasks.py', 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    print(f"Read tasks.py: {len(lines)} lines")
    
    # Create tasks directory if it doesn't exist
    os.makedirs('tasks', exist_ok=True)
    
    # Generate each task module
    for filename, content_dict in TASK_MAPPINGS.items():
        filepath = os.path.join('tasks', filename)
        file_content = create_task_file(filename, content_dict, lines)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        tasks_count = len(content_dict.get('tasks', []))
        helpers_count = len(content_dict.get('helpers', []))
        funcs_count = len(content_dict.get('functions', []))
        total = tasks_count + helpers_count + funcs_count
        
        print(f"Created {filepath} ({total} items: {tasks_count} tasks, {helpers_count} helpers, {funcs_count} functions)")
    
    print("\n✓ All task modules created successfully!")
    print("\nNext steps:")
    print("1. Review the generated files")
    print("2. Fix any cross-module imports")
    print("3. Run Django check")
    print("4. Run tests")

if __name__ == '__main__':
    main()
