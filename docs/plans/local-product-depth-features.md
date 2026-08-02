# Local Product Depth Features

## Overview

Mở rộng AI Startup Coach theo hướng FE-first nhưng vẫn giữ mô hình local single-user và Journey-first. Đợt này biến dữ liệu đã có thành trải nghiệm dùng lại được: nhớ đúng nơi đang làm, xem và khôi phục lịch sử ý tưởng, theo dõi tiến độ, xem pitch dưới dạng slide, và xuất một hồ sơ startup tổng hợp.

Kế hoạch ưu tiên tái sử dụng các nền tảng hiện có:

- Sáu loại tài liệu đã có current version và version history.
- Backend đã sinh PDF/DOCX cho từng tài liệu.
- `funding_guide.pitch_outline` đã chứa dữ liệu slide.
- Backend đã tự mở chat session gần nhất khi FE không truyền `session_id`.

## Quyết định phạm vi

### Trong phạm vi

1. Tiếp tục nơi đang làm dở theo từng startup.
2. Lịch sử phát triển ý tưởng: xem version cũ, so sánh theo field và khôi phục thành version mới.
3. Dashboard/overview tiến độ gọn trong workspace, không tạo hệ thống analytics riêng.
4. Startup Report tổng hợp, có preview và xuất PDF/DOCX từ cùng dữ liệu chuẩn hóa.
5. Pitch Deck presentation view từ `pitch_outline` hiện có và xuất PDF ngang.

### Ngoài phạm vi

- Backup/restore dữ liệu local.
- Stage kiểm chứng vấn đề và liên kết version với bằng chứng/phỏng vấn.
- Trường `change_note` hoặc audit log lý do thay đổi.
- Module tài chính, dự báo doanh thu hoặc kế toán mới. “Tài chính cơ bản” trong report chỉ tổng hợp dòng doanh thu, cơ cấu chi phí và ngân sách marketing đang có.
- Sinh lại pitch bằng một luồng AI mới; pitch tiếp tục được tạo trong stage Gọi vốn hiện tại.
- Xuất PPTX, theme editor, drag-and-drop slide hoặc rich-text editor.
- Một trang dashboard quản trị tách khỏi Journey.

## Các quyết định thiết kế

- Khôi phục version không đổi cờ `is_current` trên bản cũ. Backend sao chép nội dung version được chọn thành version mới nhất để lịch sử luôn bất biến.
- So sánh version thực hiện ở FE vì API history đã trả nội dung đầy đủ. Diff theo field; scalar hiển thị trước/sau, list hiển thị phần thêm/bớt, object/list phức tạp fallback về trước/sau đã chuẩn hóa. Không thêm thư viện diff.
- Workspace state lưu trong `localStorage`; dữ liệu nghiệp vụ và chat vẫn lấy từ backend. ID startup không còn tồn tại phải được bỏ qua an toàn.
- Dashboard chỉ hiển thị dữ liệu có thể chứng minh: stage hiện tại, số tài liệu hiện có, tổng số version và các cập nhật tài liệu gần đây. Không suy diễn thời gian học hay phần trăm chất lượng nội dung.
- Startup Report và file export dùng cùng `ReportSection` chuẩn hóa ở backend. “Tổng quan ý tưởng” được dẫn xuất từ Lean Canvas hiện tại; không thêm bảng `idea` mới.
- Pitch Deck dùng `funding_guide.pitch_outline`; presentation view là một chế độ con của tài liệu Gọi vốn, không phải document type hay stage mới.

## API và cấu trúc dữ liệu mục tiêu

### Khôi phục version

```text
POST /startups/{startup_id}/documents/{doc_type}/versions/{version}/restore
```

Response dùng lại `DocumentResponse`. Nếu version không tồn tại trả `404`; document type không hợp lệ trả `400`. Thành công tạo version `max(version) + 1` và đánh dấu bản mới là current trong cùng transaction/parent-row lock đang dùng khi lưu tài liệu.

### Startup overview

```text
GET /startups/{startup_id}/overview
```

Response tối thiểu:

```json
{
  "current_stage": "swot",
  "journey_completed_steps": 3,
  "journey_total_steps": 8,
  "completed_documents": 3,
  "total_documents": 6,
  "total_versions": 7,
  "documents": [
    {
      "doc_type": "lean_canvas",
      "exists": true,
      "version": 3,
      "updated_at": "2026-08-02T10:00:00Z"
    }
  ],
  "recent_updates": []
}
```

`recent_updates` chỉ chứa tối đa năm version tài liệu mới nhất. Stage transition chưa có audit table nên không xuất hiện trong timeline.

### Startup Report

```text
GET /startups/{startup_id}/report
GET /startups/{startup_id}/report/export?format=pdf&sections=overview,lean_canvas,...
```

Report trả danh sách section có thứ tự cố định:

1. `overview`: problem, customer segment, solution và value proposition từ Lean Canvas.
2. `lean_canvas`.
3. `bmc`.
4. `swot`.
5. `product_plan`.
6. `marketing`.
7. `basic_finance`: revenue streams, cost structure và marketing budget hiện có.
8. `pitch_outline`: lấy từ Funding Guide.

Mỗi section có `key`, `title`, `available` và `content`. Preview vẫn cho thấy section chưa có dữ liệu; export chỉ nhận các key hợp lệ do người dùng chọn. Nếu không truyền `sections`, export tất cả section đang available.

### Pitch Deck export

```text
GET /startups/{startup_id}/pitch-deck/export?format=pdf
```

Endpoint chỉ hỗ trợ PDF trong đợt này, mỗi slide là một trang landscape. Nếu chưa có `pitch_outline`, trả `404` với thông báo có thể hiển thị trực tiếp trên empty state.

## Steps

### 1. Khóa contract bằng test trước khi triển khai

- Mở rộng `tests/api/test_routes.py` cho restore version, overview, report preview/export và pitch PDF export.
- Mở rộng `tests/services/test_persistence_services.py` để chứng minh restore tạo version mới, giữ nguyên version nguồn và chỉ có một current version.
- Mở rộng `tests/services/test_document_export_service.py` cho report nhiều section, section selection, Unicode và pitch PDF landscape.
- Bổ sung test FE cho workspace persistence, version selection/diff/restore, overview, report và pitch navigation trước khi nối UI hoàn chỉnh.

### 2. Tiếp tục nơi đang làm dở — FE trước, không đổi backend

- Tạo `frontend/src/stores/workspacePreferencesStore.ts` dùng Zustand `persist` với schema version rõ ràng.
- Lưu `lastStartupId`; theo từng startup lưu `activeView`, `selectedDocument` và `chatDraft`.
- Sửa `frontend/src/components/AppShell.tsx` để khôi phục startup gần nhất nếu ID còn tồn tại; fallback về startup đầu tiên nếu dữ liệu cũ/stale.
- Sửa `StartupWorkspace` để không reset tab/document khi remount; stage thay đổi chỉ tự chọn document tương ứng khi người dùng chưa có lựa chọn đã lưu.
- Sửa `frontend/src/features/chat/ChatPanel.tsx` để draft được lưu theo startup, xóa sau khi gửi thành công và không chia sẻ giữa các startup.
- Giữ cơ chế chat hiện tại: request không có session ID sẽ lấy session mới nhất rồi cập nhật `chatSessionStore`; không persist message hoặc session payload vào localStorage.
- Test reload store, stale startup ID, đổi qua lại hai startup và khôi phục draft độc lập.

### 3. Hoàn thiện lịch sử phát triển ý tưởng

#### Backend

- Thêm `DocumentService.get_document_version()` và `DocumentService.restore_document_version()` trong `app/services/document_service.py`.
- Restore tái sử dụng `_insert_version_locked()` để giữ transaction, row lock và invariant version hiện tại.
- Thêm route restore trong `app/api/routes.py`; dùng `DocumentResponse` hiện có, không migration schema.

#### Frontend

- Thêm `restoreDocumentVersion()` vào `frontend/src/api/documents.ts`.
- Chuyển `frontend/src/features/documents/VersionHistory.tsx` từ danh sách tĩnh thành danh sách có nút `Xem lại`, `So sánh` và trạng thái version đang preview.
- Tạo `frontend/src/features/documents/documentDiff.ts` chứa hàm thuần so sánh hai `content` object theo field.
- Tạo `frontend/src/features/documents/VersionCompare.tsx` hiển thị field thay đổi, trước/sau, phần thêm/bớt và empty state “Không có thay đổi”.
- Sửa `frontend/src/features/documents/DocumentWorkspace.tsx` để preview version cũ mà không ghi đè current query; hiển thị banner `Bạn đang xem phiên bản X` và nút quay lại hiện tại.
- Dùng `ConfirmationDialog` trước restore. Sau thành công invalidate current document, history, overview và report query; tự chuyển về version mới current.
- Bổ sung responsive layout cho diff; trên mobile xếp trước/sau theo chiều dọc.

### 4. Thêm startup overview trong workspace

#### Backend

- Tạo `app/services/startup_overview_service.py` để aggregate sáu bảng document bằng các query count/current/recent có giới hạn, không tải toàn bộ content.
- Thêm response models `StartupOverviewResponse`, `DocumentProgressResponse` và `RecentDocumentUpdateResponse` trong `app/api/schemas.py`.
- Thêm `GET /startups/{startup_id}/overview` trong `app/api/routes.py`, tiếp tục dùng local profile ownership dependency.

#### Frontend

- Tạo `frontend/src/api/overview.ts` và types tương ứng.
- Tạo `frontend/src/features/overview/StartupOverview.tsx` đặt dưới Journey và trên content switcher.
- Trạng thái thu gọn hiển thị `x/8 giai đoạn · y/6 tài liệu · z phiên bản` và CTA tiếp tục stage hiện tại.
- Trạng thái mở rộng hiển thị progress bar, document checklist và năm cập nhật gần nhất; không thêm chart library.
- CTA mở AI Coach hoặc document hiện tại bằng callback của `StartupWorkspace`.
- Invalidate overview sau advance/set stage, chat tạo document, restore version và rename startup khi label liên quan thay đổi.

### 5. Xây Startup Report từ dữ liệu chuẩn hóa chung

#### Backend

- Tạo `app/services/startup_report_service.py` để lấy current version của sáu document và xây danh sách `ReportSection` theo thứ tự đã chốt.
- Dẫn xuất `overview` và `basic_finance` từ field hiện có; section chỉ `available=true` khi có ít nhất một giá trị thực.
- Refactor `app/services/document_export_service.py` để phần build DOCX/PDF nhận title và nhiều section dùng chung; giữ nguyên hành vi export từng document.
- Thêm `export_report()` hoặc service tương đương dùng chính danh sách section từ `StartupReportService`, tránh FE preview và file download lệch nội dung.
- Thêm schemas và hai route report trong `app/api/schemas.py` và `app/api/routes.py`.
- Validate `sections`: bỏ duplicate nhưng giữ thứ tự chuẩn; key lạ trả `422`; không có section khả dụng trả `404` cho export.

#### Frontend

- Thêm `startup_report` như một workspace tab hiển thị trong nhóm Tài liệu nhưng không đưa vào `DocumentType` gửi cho API document.
- Tạo `frontend/src/api/reports.ts` cho preview và file download.
- Tạo `frontend/src/features/reports/StartupReportWorkspace.tsx` với checklist section, trạng thái đủ/chưa đủ, A4 preview và nút PDF/DOCX.
- Tạo mapping section renderer tái sử dụng các primitive của `DocumentLayouts.tsx`; không copy nguyên component cho từng tài liệu.
- Khi section chưa có dữ liệu, hiển thị lý do và CTA mở stage/document nguồn; mặc định chỉ chọn section available.
- Invalidate report sau khi chat cập nhật document hoặc restore version.

### 6. Nâng Pitch outline thành Pitch Deck presentation

#### Backend

- Mở rộng exporter hoặc tạo `app/services/pitch_deck_export_service.py` chuyên PDF landscape; không ép logic slide vào exporter A4 của report.
- Mỗi item trong `pitch_outline` tạo đúng một trang với số slide, tiêu đề, nội dung và tên startup; đăng ký cùng Unicode font fallback hiện có.
- Thêm route pitch PDF; filename theo dạng `{startup-slug}-pitch-deck.pdf`.

#### Frontend

- Tạo `frontend/src/features/pitch/PitchDeckView.tsx` nhận `pitch_outline` đã có, không gọi AI lại.
- Trong tài liệu Gọi vốn, thêm switch `Nội dung | Trình chiếu`; mặc định giữ `Nội dung` để không phá luồng document hiện tại.
- Presentation view có danh sách slide, preview 16:9, previous/next, chỉ số `x/y`, phím mũi tên và chế độ toàn màn hình có fallback nếu Fullscreen API không khả dụng.
- Thêm `downloadPitchDeck()` vào API report/document phù hợp và nút `Tải Pitch PDF`.
- Empty state dẫn người dùng về stage Gọi vốn khi chưa có `pitch_outline`.
- Test keyboard navigation, slide boundary, fullscreen fallback, dữ liệu rỗng và download filename.

### 7. Tích hợp, polish và accessibility

- Tách `AppShell.tsx` nếu vượt quá trách nhiệm hiện tại: `StartupWorkspace`, workspace navigation và overview thành file riêng, tránh tiếp tục phình component shell.
- Gom các key React Query vào helper/constants để restore, report và overview invalidate nhất quán.
- Cập nhật `frontend/src/styles.css` cho version diff, overview, report preview và pitch 16:9 trên desktop/mobile.
- Đảm bảo tab/switch dùng đúng `role`, focus visible, dialog restore giữ focus, keyboard pitch không chặn khi đang nhập liệu và màu diff không phải tín hiệu duy nhất.
- Xử lý loading, empty, error và retry riêng cho từng feature; download có disabled/loading và toast.

### 8. Xác minh và review

- Backend: chạy test service/export/API mục tiêu, sau đó toàn bộ `pytest` nếu môi trường database sẵn sàng.
- Frontend: chạy `npm test`, `npm run typecheck` và `npm run build`.
- Manual flow desktop và mobile:
  1. Chọn startup B, mở tab Tài liệu, chọn SWOT, gõ draft; reload và xác nhận khôi phục đúng state.
  2. Xem version cũ, so sánh, restore và xác nhận xuất hiện version mới current.
  3. Mở overview và xác nhận count/timeline cập nhật sau restore.
  4. Chọn section report, kiểm tra preview rồi mở file DOCX/PDF hợp lệ với tiếng Việt.
  5. Mở pitch presentation, điều hướng bàn phím/fullscreen và tải PDF landscape.
- Rà diff cuối để không ghi đè các thay đổi local single-user/export đang tồn tại trong worktree.

## Rủi ro và cách kiểm soát

- **Worktree đang có nhiều thay đổi chưa commit:** implementation phải chỉnh hẹp đúng file, đọc lại nội dung mới nhất trước mỗi patch và không revert thay đổi ngoài scope.
- **Restore cạnh tranh với một lần AI save:** bắt buộc đi qua parent-row lock và test hai lần ghi tuần tự chỉ còn một current version.
- **Diff JSON không có schema UI chung:** dùng field-level diff bảo thủ; object/list không nhận diện được item thì hiển thị trước/sau thay vì đoán sai.
- **Report thiếu dữ liệu:** preview nói rõ section nào chưa sẵn sàng; export mặc định bỏ section thiếu thay vì tạo hồ sơ dài toàn placeholder.
- **Overview count tốn query:** service aggregate count/current metadata, giới hạn recent updates và không tải content.
- **Pitch outline không đủ 8–10 slide:** UI hiển thị đúng số slide thực tế; không tự bịa thêm slide ở FE.
- **PDF tiếng Việt/landscape:** test signature, page size và text extraction cơ bản; giữ font Unicode fallback hiện tại.
- **localStorage stale hoặc hỏng JSON:** Zustand persist có version/migration và fallback an toàn về state mặc định.

## Completion criteria

- Reload ứng dụng mở đúng startup, view, document và chat draft gần nhất; dữ liệu stale không làm crash.
- Người dùng xem được mọi version, thấy diff có ý nghĩa và restore tạo một version mới mà không mất lịch sử.
- Overview hiển thị count đúng với database và recent updates đổi sau khi có version mới.
- Startup Report preview và file PDF/DOCX cùng thứ tự, heading và nội dung section đã chọn; section thiếu được thể hiện rõ trên UI.
- Pitch outline hiện được dưới dạng slide 16:9, điều hướng được bằng chuột/bàn phím/fullscreen và tải được PDF landscape có tiếng Việt.
- Không có backup/restore, PPTX, module tài chính mới, validation/evidence hoặc dashboard analytics nằm ngoài scope bị kéo vào implementation.
- Backend tests liên quan, frontend tests, typecheck và production build đều pass.
