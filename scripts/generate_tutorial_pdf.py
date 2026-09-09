from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "AIEvalOps_Python保姆级教程.md"
OUTPUT = ROOT / "output" / "pdf" / "AIEvalOps_Python保姆级教程.pdf"


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path(r"C:\Windows\Fonts\Deng.ttf"), Path(r"C:\Windows\Fonts\Dengb.ttf")),
        (Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"), Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("Chinese", str(regular)))
            pdfmetrics.registerFont(TTFont("Chinese-Bold", str(bold)))
            return "Chinese", "Chinese-Bold"
    raise FileNotFoundError("没有找到可用的中文字体。")


FONT, BOLD_FONT = register_fonts()
CODE_FONT = FONT


def inline_markup(text: str) -> str:
    text = html.escape(text, quote=False)
    tick = chr(96)
    text = re.sub(
        re.escape(tick) + r"([^" + re.escape(tick) + r"]+)" + re.escape(tick),
        r'<font name="Chinese-Bold" color="#0f4c81">\1</font>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="#1565c0">\1</link>', text)
    return text


class CodeBlock(Flowable):
    """带浅色背景、支持分页和中文的代码块。"""

    def __init__(self, text: str, font_name: str = CODE_FONT, font_size: float = 7.7):
        super().__init__()
        self.text = text.replace("\t", "    ")
        self.font_name = font_name
        self.font_size = font_size
        self.leading = font_size * 1.42
        self.padding = 5
        self._lines: list[str] = []

    def _wrap_lines(self, width: float) -> list[str]:
        usable = max(width - self.padding * 2, 40)
        output: list[str] = []
        for source_line in (self.text.splitlines() or [""]):
            if source_line == "":
                output.append("")
                continue
            current = ""
            for char in source_line:
                trial = current + char
                if (
                    current
                    and pdfmetrics.stringWidth(
                        trial,
                        self.font_name,
                        self.font_size,
                    )
                    > usable
                ):
                    output.append(current)
                    current = char
                else:
                    current = trial
            output.append(current)
        return output

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        self._lines = self._wrap_lines(avail_width)
        self.height = len(self._lines) * self.leading + self.padding * 2
        return self.width, self.height

    def split(self, avail_width: float, avail_height: float) -> list[Flowable]:
        if not self._lines:
            self.wrap(avail_width, avail_height)
        max_lines = int((avail_height - self.padding * 2) // self.leading)
        if max_lines < 1:
            return []
        if len(self._lines) <= max_lines:
            return [self]
        first = CodeBlock("\n".join(self._lines[:max_lines]), self.font_name, self.font_size)
        rest = CodeBlock("\n".join(self._lines[max_lines:]), self.font_name, self.font_size)
        return [first, rest]

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#f5f7fa"))
        canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
        canvas.roundRect(0, 0, self.width, self.height, 3, stroke=1, fill=1)
        canvas.setFillColor(colors.HexColor("#263238"))
        canvas.setFont(self.font_name, self.font_size)
        text = canvas.beginText(self.padding, self.height - self.padding - self.font_size)
        text.setLeading(self.leading)
        for line in self._lines:
            text.textLine(line)
        canvas.drawText(text)
        canvas.restoreState()


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TutorialTitle",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=22,
            leading=29,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#12355b"),
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "TutorialH2",
            parent=base["Heading1"],
            fontName=BOLD_FONT,
            fontSize=16,
            leading=21,
            textColor=colors.HexColor("#12355b"),
            spaceBefore=13,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "TutorialH3",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=12.5,
            leading=17,
            textColor=colors.HexColor("#1e5a88"),
            spaceBefore=9,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "TutorialBody",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.4,
            leading=14,
            textColor=colors.HexColor("#243447"),
            wordWrap="CJK",
            spaceAfter=5,
        ),
        "quote": ParagraphStyle(
            "TutorialQuote",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.5,
            leading=14,
            leftIndent=10,
            rightIndent=6,
            borderColor=colors.HexColor("#9fbad0"),
            borderWidth=1,
            borderPadding=6,
            backColor=colors.HexColor("#f2f7fb"),
            textColor=colors.HexColor("#36536b"),
            wordWrap="CJK",
            spaceBefore=3,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "TutorialBullet",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=12.4,
            textColor=colors.HexColor("#243447"),
            wordWrap="CJK",
            spaceAfter=0,
        ),
        "code_label": ParagraphStyle(
            "CodeLabel",
            parent=base["BodyText"],
            fontName=BOLD_FONT,
            fontSize=7.4,
            leading=9,
            textColor=colors.HexColor("#6b7785"),
            spaceBefore=4,
            spaceAfter=2,
        ),
        "table": ParagraphStyle(
            "TutorialTable",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.3,
            leading=11,
            textColor=colors.HexColor("#243447"),
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TutorialTableHeader",
            parent=base["BodyText"],
            fontName=BOLD_FONT,
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
            wordWrap="CJK",
        ),
    }


def is_special(line: str) -> bool:
    return (
        not line.strip()
        or line.startswith("#")
        or line.startswith(">")
        or line.startswith("~~~")
        or re.match(r"^\s*[-*]\s+", line) is not None
        or re.match(r"^\s*\|", line) is not None
        or line.strip() in {"---", "***"}
    )


def parse_table(lines: list[str], start: int, styles: dict[str, ParagraphStyle], width: float):
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        raw = lines[i].strip().strip("|")
        rows.append([cell.strip() for cell in raw.split("|")])
        i += 1
    if len(rows) >= 2 and all(re.match(r"^:?-+:?$", cell.replace(" ", "")) for cell in rows[1]):
        rows.pop(1)
    if not rows:
        return None, i
    col_count = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (col_count - len(row)))
    data = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if row_index == 0 else styles["table"]
        data.append([Paragraph(inline_markup(cell), style) for cell in row])
    col_width = width / col_count
    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#286090")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ]
        )
    )
    return table, i


def build_story(markdown: str, styles: dict[str, ParagraphStyle], width: float) -> list[Flowable]:
    lines = markdown.splitlines()
    story: list[Flowable] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("~~~"):
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("~~~"):
                code_lines.append(lines[i].rstrip("\n"))
                i += 1
            if i < len(lines):
                i += 1
            # 语言标签已经写在 Markdown 围栏中；PDF 中不单独显示，避免标签落在页底而代码移到下一页。
            story.append(CodeBlock("\n".join(code_lines)))
            story.append(Spacer(1, 4))
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            style = styles["title"] if level == 1 else styles["h2"] if level == 2 else styles["h3"]
            story.append(Paragraph(inline_markup(heading.group(2)), style))
            i += 1
            continue
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(lines[i][1:].strip())
                i += 1
            story.append(Paragraph(inline_markup("<br/>".join(quote_lines)), styles["quote"]))
            continue
        if line.lstrip().startswith("|"):
            table, i = parse_table(lines, i, styles, width)
            if table:
                story.append(table)
                story.append(Spacer(1, 7))
            continue
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i]).strip()
                item = re.sub(
                    r"^\[([ xX])\]\s*",
                    lambda match: (
                        "☑ "
                        if match.group(1).lower() == "x"
                        else "☐ "
                    ),
                    item,
                )
                items.append(ListItem(Paragraph(inline_markup(item), styles["bullet"])))
                i += 1
            story.append(
                ListFlowable(
                    items,
                    bulletType="bullet",
                    leftIndent=13,
                    bulletFontName=FONT,
                    bulletFontSize=7,
                )
            )
            story.append(Spacer(1, 1))
            continue
        if line.strip() in {"---", "***"}:
            story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#cbd5df")))
            story.append(Spacer(1, 7))
            i += 1
            continue
        paragraph_lines = [line.strip()]
        i += 1
        while i < len(lines) and not is_special(lines[i]):
            paragraph_lines.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline_markup(" ".join(paragraph_lines)), styles["body"]))
    return story


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    page_width, page_height = A4
    canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin,
        page_height - 16 * mm,
        page_width - doc.rightMargin,
        page_height - 16 * mm,
    )
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(colors.HexColor("#718096"))
    canvas.drawString(doc.leftMargin, page_height - 12 * mm, "AIEvalOps · Python 测试开发教程")
    canvas.drawRightString(page_width - doc.rightMargin, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    markdown = SOURCE.read_text(encoding="utf-8")
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=22 * mm,
        bottomMargin=16 * mm,
        title="AIEvalOps：Python 测试开发保姆级教程",
        author="AIEvalOps",
        subject="Python、FastAPI、Pytest、Promptfoo 测试开发教程",
        allowSplitting=1,
    )
    story = build_story(markdown, styles, doc.width)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(f"generated: {OUTPUT}")


if __name__ == "__main__":
    main()
