from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class DocumentChunk:
    source: str
    content: str
    chunk_index: int
    page: int | None = None
    chunk_id: str = ""


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
        raise FileNotFoundError(f"知识库目录不存在：{knowledge_dir}")

    if not knowledge_dir.is_dir():
        raise NotADirectoryError(f"知识库路径不是目录：{knowledge_dir}")

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
        raise ValueError(f"知识库目录中没有可读取的 Markdown 内容：{knowledge_dir}")

    return chunks


def build_chunk_id(
    source: str,
    page: int | None,
    chunk_index: int,
    content: str,
) -> str:
    """根据来源和内容生成稳定的片段 ID。"""

    raw = f"{source}|{page}|{chunk_index}|{content}"
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def load_documents(
    knowledge_dir: Path,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[DocumentChunk]:
    """递归读取知识库中的 Markdown 和 PDF，并切分为片段。"""

    if not knowledge_dir.exists():
        raise FileNotFoundError(f"知识库目录不存在：{knowledge_dir}")

    if not knowledge_dir.is_dir():
        raise NotADirectoryError(f"知识库路径不是目录：{knowledge_dir}")

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")

    # rglob("*") 会递归查看 knowledge 及其所有子目录。
    document_paths = sorted(
        (
            path
            for path in knowledge_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".pdf"}
        ),
        key=lambda path: path.relative_to(knowledge_dir).as_posix(),
    )

    chunks: list[DocumentChunk] = []

    for document_path in document_paths:
        # 例如：
        # knowledge/refund.md     -> refund.md
        # knowledge/raw/privacy.pdf -> raw/privacy.pdf
        source = document_path.relative_to(knowledge_dir).as_posix()

        if document_path.suffix.lower() == ".md":
            text = document_path.read_text(encoding="utf-8")

            # Markdown 没有页码，所以使用 None。
            sections: list[tuple[int | None, str]] = [(None, text)]

        else:
            reader = PdfReader(str(document_path))

            # enumerate(..., start=1) 使页码从 1 开始，
            # 与人阅读 PDF 时看到的页码习惯一致。
            sections = [
                (
                    page_number,
                    pdf_page.extract_text() or "",
                )
                for page_number, pdf_page in enumerate(
                    reader.pages,
                    start=1,
                )
            ]

            if not any(text.strip() for _, text in sections):
                raise ValueError(f"PDF 无可提取文字：{source}；请确认它不是扫描图片 PDF")

        # 每个文件单独从 0 开始编号。
        chunk_index = 0

        for page_number, text in sections:
            page_chunks = split_text(
                text=text,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for content in page_chunks:
                chunks.append(
                    DocumentChunk(
                        source=source,
                        content=content,
                        chunk_index=chunk_index,
                        page=page_number,
                        chunk_id=build_chunk_id(
                            source=source,
                            page=page_number,
                            chunk_index=chunk_index,
                            content=content,
                        ),
                    )
                )

                chunk_index += 1

    if not chunks:
        raise ValueError(f"知识库中没有可读取的文档内容：{knowledge_dir}")

    return chunks
