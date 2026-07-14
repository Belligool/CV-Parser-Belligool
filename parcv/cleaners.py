import re
import unicodedata

class ResumeCleaner:
    BULLETS = [
        "•",
        "●",
        "◦",
        "▪",
        "■",
        "□",
        "►",
        "▸",
        "▶",
        "○",
        "◉",
        "◆",
        "◇",
        "▪",
        "▫",
    ]
    DASHES = {
        "–": "-",
        "—": "-",
        "−": "-",
        "-": "-",
    }
    QUOTES = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
    }
    PDF_ARTIFACTS = [
        "\uf0b7",
    ]

    def normalize_unicode(self, text):
        return unicodedata.normalize("NFKC", text)
    def normalize_whitespace(self, text):
        text = text.replace("\t", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    def normalize_quotes(self, text):
        for old, new in self.QUOTES.items():
            text = text.replace(old, new)
        return text
    def normalize_dashes(self, text):
        for old, new in self.DASHES.items():
            text = text.replace(old, new)
        text = re.sub(r"\s*-\s*", " - ", text)
        return text
    def remove_bullets(self, text):
        text = text.lstrip()
        for bullet in self.BULLETS:
            if text.startswith(bullet):
                text = text[len(bullet):].strip()
        return text
    def remove_pdf_artifacts(self, text):
        for artifact in self.PDF_ARTIFACTS:
            text = text.replace(artifact, " ")
        text = re.sub(r"\(cid:\d+\)", " ", text)
        return text
    
    def clean_resume_lines(self, lines):
        cleaned = []
        for line in lines:
            line = self.normalize_unicode(line)
            line = self.normalize_whitespace(line)
            line = self.normalize_quotes(line)
            line = self.normalize_dashes(line)
            line = self.remove_bullets(line)
            line = self. remove_pdf_artifacts(line)
            line = self.remove_pdf_artifacts(line)
            if line:
                cleaned.append(line)
        return cleaned