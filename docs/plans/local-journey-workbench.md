# Local Journey Workbench

## Overview

Chuyển AI Startup Coach thành công cụ local single-user: lần đầu chỉ hỏi tên, không có login/logout; mỗi startup có thể đổi tên và hiển thị tiến độ; Journey nằm ngang phía trên; khu vực dưới chỉ còn AI Coach và Tài liệu; tài liệu có bản xem A4 và tải được PDF/DOCX.

### Trong phạm vi

- Hồ sơ local duy nhất, tự khởi tạo trên dữ liệu hiện có và cho phép cập nhật tên.
- Các API startup/chat/stage/document dùng hồ sơ local, không yêu cầu Bearer token.
- Đổi tên startup và hiển thị stage, tiến độ, thời gian cập nhật trong danh sách.
- FE không còn login, signup, logout, brand mark, avatar startup hay nhãn “Đang chạy local”.
- Journey-first responsive; desktop là process ngang, mobile là stage hiện tại kèm danh sách cuộn ngang.
- Hai chế độ nội dung: AI Coach mặc định và Tài liệu.
- Tài liệu trình bày như trang A4 và tải PDF/DOCX từ backend.

### Ngoài phạm vi

- Ảnh/avatar startup, upload file, cộng tác nhiều người, truy cập LAN/mobile từ máy khác.
- Xóa migration/bảng auth cũ hoặc migration phá dữ liệu hiện có.
- Trình soạn thảo rich-text và chỉnh sửa tài liệu ngay trong app.
- Branding cho đội phát triển.

## Steps — Red → Green → Refactor

1. **Red — hợp đồng local profile và startup**
   - Thêm test backend cho GET/PUT local profile, truy cập startup không token và PATCH đổi tên startup.
   - Thêm test frontend cho onboarding tên, shell không auth, đổi tên và Journey-first.
   - Chạy test mục tiêu, xác nhận thất bại vì chức năng chưa tồn tại.
2. **Green — local profile và API single-user**
   - Thêm dependency/service lấy hoặc tạo local user; thêm profile schemas/routes.
   - Chuyển ownership dependency sang local user và thêm API đổi tên startup.
   - Giữ auth code/database cũ để tránh migration phá dữ liệu, nhưng FE không còn gọi auth.
3. **Red — export tài liệu**
   - Thêm test thuần cho nội dung chuẩn hóa, MIME/filename và chữ ký file PDF/DOCX.
   - Thêm test frontend cho nút tải hai định dạng và URL export.
4. **Green — document export**
   - Thêm document export service dùng cùng một cấu trúc heading/section cho PDF và DOCX.
   - Thêm endpoint tải file và client helper; bổ sung dependency tạo file.
5. **Green — Journey-first frontend**
   - Thêm onboarding profile local và API/store/query tương ứng.
   - Refactor App/AppShell: wordmark chữ, account copy, danh sách startup không avatar, rename inline.
   - Đưa StageStepper lên đầu workspace; rút tab còn AI Coach/Tài liệu; chat mặc định và composer sticky.
   - Chuẩn hóa document preview thành A4, thêm nút PDF/DOCX và các trạng thái loading/empty/toast.
6. **Refactor và xác minh**
   - Loại bỏ import/state/CSS auth không còn được dùng trong runtime; gom mapping nhãn tài liệu dùng chung.
   - Giới hạn port compose vào `127.0.0.1` cho mô hình không-auth local-only.
   - Chạy backend unit/API tests liên quan, toàn bộ frontend tests, typecheck và production build.
   - Rà diff để không ghi đè thay đổi ngoài phạm vi và thực hiện code review cuối.

## Risks

- Auth cũ gắn ownership qua `user_id`: giảm rủi ro bằng local user ổn định thay vì migration xóa cột.
- PDF tiếng Việt cần font Unicode trong runtime: exporter phải đăng ký font tương thích và có fallback được test.
- Download file không thể dùng JSON parser hiện tại: client export dùng `fetch`/Blob riêng và kiểm tra lỗi HTTP.
- Workspace đang có thay đổi chưa commit: chỉ chỉnh các file nằm trong plan và không revert thay đổi hiện có.

## Completion criteria

- Người dùng mới chỉ nhập tên một lần; lần sau vào thẳng workspace và có thể đổi tên trong app.
- Không có login/signup/logout, brand mark, avatar startup hoặc nhãn local trên UI runtime.
- Startup đổi tên được; danh sách có tên, stage, tiến độ và thời gian cập nhật.
- Journey hiển thị trên cùng; AI Coach là nội dung mặc định; Tài liệu là chế độ thứ hai.
- Tài liệu hiện như trang A4 và tải được file mở hợp lệ với đuôi `.pdf` và `.docx`.
- Các API chính hoạt động không cần Authorization và Docker chỉ publish trên localhost.
- Test, typecheck và build được liệt kê ở bước 6 đều pass.
