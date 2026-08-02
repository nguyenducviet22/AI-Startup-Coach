import { KeyboardEvent, useRef, useState } from "react";

import { downloadPitchDeck } from "../../api/reports";
import { useToastStore } from "../../stores/toastStore";

export type PitchSlide = { slide_title?: string; content?: string };

export function PitchDeckView({ startupId, startupName, slides }: { startupId: string; startupName: string; slides: PitchSlide[] }) {
  const [index, setIndex] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const deckRef = useRef<HTMLDivElement>(null);
  const showToast = useToastStore((state) => state.showToast);
  if (!slides.length) return <div className="document-empty"><div className="empty-icon" aria-hidden="true">▭</div><h3>Chưa có Pitch outline</h3><p>Hoàn thành giai đoạn Gọi vốn để AI Coach tạo nội dung slide từ dữ liệu Journey.</p></div>;
  const slide = slides[Math.min(index, slides.length - 1)];

  function move(delta: number) {
    setIndex((current) => Math.max(0, Math.min(slides.length - 1, current + delta)));
    deckRef.current?.focus();
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    if (event.key === "ArrowRight") { event.preventDefault(); move(1); }
    if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); }
  }
  async function enterFullscreen() {
    try {
      if (!deckRef.current?.requestFullscreen) throw new Error("Fullscreen unavailable");
      await deckRef.current.requestFullscreen();
    } catch {
      showToast("Trình duyệt không hỗ trợ chế độ toàn màn hình tại đây.", "info");
    }
  }
  async function download() {
    setDownloading(true);
    try { await downloadPitchDeck(startupId); showToast("Đã tải Pitch Deck PDF.", "success"); }
    catch { showToast("Không thể tải Pitch Deck. Vui lòng thử lại.", "error"); }
    finally { setDownloading(false); }
  }

  return <section className="pitch-deck" aria-label="Pitch Deck">
    <div className="pitch-toolbar"><span>{index + 1}/{slides.length}</span><div><button type="button" className="text-button" onClick={() => void enterFullscreen()}>Toàn màn hình</button><button type="button" className="secondary-button compact-button" disabled={downloading} onClick={() => void download()}>{downloading ? "Đang tạo..." : "Tải Pitch PDF"}</button></div></div>
    <div className="pitch-layout">
      <nav className="pitch-slide-list" aria-label="Danh sách slide">{slides.map((item, slideIndex) => <button type="button" className={slideIndex === index ? "selected" : ""} aria-current={slideIndex === index ? "true" : undefined} onClick={() => setIndex(slideIndex)} key={`${item.slide_title}-${slideIndex}`}><span>{String(slideIndex + 1).padStart(2, "0")}</span>{item.slide_title || `Slide ${slideIndex + 1}`}</button>)}</nav>
      <div className="pitch-stage" ref={deckRef} tabIndex={0} onKeyDown={onKeyDown}>
        <article className="pitch-slide"><span className="pitch-slide-number">{String(index + 1).padStart(2, "0")}</span><h3>{slide.slide_title || `Slide ${index + 1}`}</h3><p>{slide.content || "Chưa có nội dung."}</p><small>{startupName}</small></article>
        <div className="pitch-navigation"><button type="button" className="secondary-button" disabled={index === 0} aria-label="Slide trước" onClick={() => move(-1)}>← Trước</button><button type="button" className="secondary-button" disabled={index === slides.length - 1} aria-label="Slide tiếp" onClick={() => move(1)}>Tiếp →</button></div>
      </div>
    </div>
  </section>;
}
