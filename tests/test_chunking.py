import unittest
from dockdesk.chunking import chunk_code, _chunk_python

class TestChunking(unittest.TestCase):
    def test_chunk_python(self):
        # Create a large python file string
        pad = "\\n# " + "A" * 100
        long_pad = pad * 20  # ~2000 chars

        code = f"""class Processor:
    def process(self):
        pass{long_pad}

def some_func():
    return True
"""
        
        # Max chars = 1000
        chunks = chunk_code("test.py", code, max_chars=1000)
        
        # It should split the file. Since the class Processor is very large, it should be split into multiple line-based chunks.
        # But 'some_func' should be preserved intact in its own chunk at the end.
        
        self.assertTrue(len(chunks) > 1, "File should be split into multiple chunks")
        
        # The last chunk should contain some_func
        last_chunk = chunks[-1]
        self.assertIn("some_func", last_chunk["text"])
        self.assertIn("return True", last_chunk["text"])

        # Check line numbers
        total_lines = len(code.splitlines())
        self.assertEqual(chunks[-1]["end_line"], total_lines, "Last chunk should end at the last line of the file")
        
        # Check continuity
        last_end = 0
        for chunk in chunks:
            self.assertEqual(chunk["start_line"], last_end + 1, "Chunks should be continuous")
            last_end = chunk["end_line"]

    def test_chunk_fallback(self):
        code = "line 1\nline 2\nline 3\nline 4"
        chunks = chunk_code("test.txt", code, max_chars=15) # Small limit
        
        self.assertTrue(len(chunks) > 1)
        self.assertEqual(chunks[0]["start_line"], 1)
        self.assertEqual(chunks[-1]["end_line"], 4)
        
        last_end = 0
        for chunk in chunks:
            self.assertEqual(chunk["start_line"], last_end + 1)
            last_end = chunk["end_line"]

if __name__ == "__main__":
    unittest.main()
