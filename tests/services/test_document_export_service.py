from io import BytesIO
from zipfile import ZipFile

from app.services.document_export_service import DocumentExportService


CONTENT = {
    "strengths": ["Hiểu nhu cầu sinh viên"],
    "weaknesses": ["Nguồn lực hạn chế"],
    "opportunities": ["Thị trường đang tăng trưởng"],
    "threats": ["Đối thủ lớn"],
}


def test_docx_export_is_valid_office_archive_with_normalized_sections() -> None:
    exported = DocumentExportService().export(
        startup_name="EcoLearn",
        doc_type="swot",
        content=CONTENT,
        file_format="docx",
    )

    assert exported.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert exported.filename == "ecolearn-swot.docx"
    with ZipFile(BytesIO(exported.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "EcoLearn" in document_xml
    assert "Điểm mạnh" in document_xml
    assert "Hiểu nhu cầu sinh viên" in document_xml


def test_pdf_export_has_pdf_signature_and_download_name() -> None:
    exported = DocumentExportService().export(
        startup_name="EcoLearn",
        doc_type="swot",
        content=CONTENT,
        file_format="pdf",
    )

    assert exported.media_type == "application/pdf"
    assert exported.filename == "ecolearn-swot.pdf"
    assert exported.content.startswith(b"%PDF-")


def test_pitch_deck_export_creates_landscape_pdf() -> None:
    exported = DocumentExportService().export_pitch_deck(
        startup_name="EcoLearn",
        slides=[
            {"slide_title": "Vấn đề", "content": "Sinh viên khó duy trì lịch học."},
            {"slide_title": "Giải pháp", "content": "Một coach học tập nhẹ nhàng."},
        ],
    )

    assert exported.content.startswith(b"%PDF-")
    assert exported.media_type == "application/pdf"
    assert exported.filename == "ecolearn-pitch-deck.pdf"
