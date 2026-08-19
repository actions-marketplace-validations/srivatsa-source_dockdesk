import os
import ast

def _split_by_lines(content: str, start_line: int, max_chars: int) -> list[dict]:
    """Fallback chunker that splits on blank lines (or hard line breaks if needed)."""
    lines = content.splitlines(keepends=True)
    chunks = []
    current_chunk = []
    current_chars = 0
    current_start = start_line

    for i, line in enumerate(lines):
        line_len = len(line)
        # If adding this line exceeds limit and we have some content, yield chunk
        if current_chars + line_len > max_chars and current_chunk:
            # Try to break on a blank line if possible by walking backwards
            break_idx = len(current_chunk)
            for j in range(len(current_chunk) - 1, -1, -1):
                if not current_chunk[j].strip():
                    break_idx = j + 1
                    break
            
            if break_idx == 0 or break_idx == len(current_chunk):
                # Hard break at current line
                break_idx = len(current_chunk)
            
            chunk_text = "".join(current_chunk[:break_idx])
            chunks.append({
                "text": chunk_text,
                "start_line": current_start,
                "end_line": current_start + break_idx - 1
            })
            
            # Start new chunk
            rem = current_chunk[break_idx:]
            current_chunk = rem + [line]
            current_start = current_start + break_idx
            current_chars = sum(len(c) for c in current_chunk)
        else:
            current_chunk.append(line)
            current_chars += line_len

    if current_chunk:
        chunks.append({
            "text": "".join(current_chunk),
            "start_line": current_start,
            "end_line": current_start + len(current_chunk) - 1
        })
        
    return chunks

def _chunk_python(content: str, max_chars: int) -> list[dict]:
    """AST-aware chunker for Python."""
    try:
        tree = ast.parse(content)
    except Exception:
        # Fallback if invalid syntax
        return _split_by_lines(content, 1, max_chars)

    lines = content.splitlines(keepends=True)
    
    # Identify boundaries for classes and functions
    boundaries = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            boundaries.append((node.lineno, node.end_lineno))
            
    # Sort boundaries
    boundaries.sort(key=lambda x: x[0])
    
    chunks = []
    last_line = 1
    
    for start, end in boundaries:
        if start > last_line:
            # Add gap code
            gap = "".join(lines[last_line - 1:start - 1])
            if gap.strip():
                if len(gap) > max_chars:
                    chunks.extend(_split_by_lines(gap, last_line, max_chars))
                else:
                    chunks.append({"text": gap, "start_line": last_line, "end_line": start - 1})
        
        # Add node code
        node_code = "".join(lines[start - 1:end])
        if len(node_code) > max_chars:
            chunks.extend(_split_by_lines(node_code, start, max_chars))
        else:
            chunks.append({"text": node_code, "start_line": start, "end_line": end})
            
        last_line = end + 1
        
    # Add trailing code
    if last_line <= len(lines):
        gap = "".join(lines[last_line - 1:])
        if gap.strip():
            if len(gap) > max_chars:
                chunks.extend(_split_by_lines(gap, last_line, max_chars))
            else:
                chunks.append({"text": gap, "start_line": last_line, "end_line": len(lines)})
                
    return chunks

def chunk_code(file_path: str, content: str, max_chars: int = 2000) -> list[dict]:
    """
    Splits code into chunks respecting function/class boundaries where possible.
    Returns list of dicts: {'text': str, 'start_line': int, 'end_line': int}
    """
    if len(content) <= max_chars:
        lines_count = len(content.splitlines())
        return [{"text": content, "start_line": 1, "end_line": max(1, lines_count)}]
        
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.py':
        return _chunk_python(content, max_chars)
        
    # Fallback for non-python files
    return _split_by_lines(content, 1, max_chars)
