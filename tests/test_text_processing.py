import unittest

from app.text_processing import build_chunks, normalize_text, split_sentences


class TextProcessingTests(unittest.TestCase):
    def test_normalize_removes_invisible_pdf_artifacts(self) -> None:
        self.assertEqual(normalize_text("\ufeffभारत\u00a0रत्न\u200b"), "भारत रत्न")

    def test_normalize_removes_unmapped_pdf_glyph_marker(self) -> None:
        self.assertEqual(normalize_text("अ\x00ुल"), "अुल")

    def test_hindi_danda_creates_sentence_boundary(self) -> None:
        self.assertEqual(split_sentences("पहला वाक्य। दूसरा वाक्य।"), ["पहला वाक्य।", "दूसरा वाक्य।"])

    def test_page_section_and_chunk_id_are_saved(self) -> None:
        pages = [(7, "अध्याय 1\nयह पहला वाक्य है। यह दूसरा वाक्य है।")]
        chunks = build_chunks(pages, max_words=20, overlap_words=3)
        self.assertEqual(chunks[0].page, 7)
        self.assertEqual(chunks[0].section, "अध्याय 1")
        self.assertEqual(chunks[0].chunk_id, "chunk-0001")


if __name__ == "__main__":
    unittest.main()
