from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentChunk:
    """
    知识库中的一个文本片段。
    """

    source: str
    content: str
    chunk_index: int


def split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[str]:
    """
    将长文本切成多个片段。

    chunk_size:
        每个片段的最大字符数。

    overlap:
        相邻片段重叠的字符数，避免一句话刚好被切断。
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")

    normalized_text = text.replace("\r\n", "\n").strip()

    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

    return chunks


def load_markdown_documents(
    knowledge_dir: Path,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[DocumentChunk]:
    """
    读取知识库目录下的所有 Markdown 文件，
    并将它们切分成 DocumentChunk 列表。
    """

    if not knowledge_dir.exists():
        raise FileNotFoundError(
            f"知识库目录不存在：{knowledge_dir}"
        )

    if not knowledge_dir.is_dir():
        raise NotADirectoryError(
            f"知识库路径不是目录：{knowledge_dir}"
        )

    chunks: list[DocumentChunk] = []

    markdown_files = sorted(knowledge_dir.glob("*.md"))

    for markdown_file in markdown_files:
        text = markdown_file.read_text(
            encoding="utf-8",
        )

        file_chunks = split_text(
            text=text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, content in enumerate(file_chunks):
            chunks.append(
                DocumentChunk(
                    source=markdown_file.name,
                    content=content,
                    chunk_index=index,
                )
            )

    if not chunks:
        raise ValueError(
            f"知识库目录中没有可读取的 Markdown 内容：{knowledge_dir}"
        )

    return chunks