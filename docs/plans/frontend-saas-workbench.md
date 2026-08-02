# Frontend SaaS Workbench Upgrade

## Overview

Nâng cấp toàn bộ frontend thành một SaaS workbench tiếng Việt dành cho sinh viên mới khởi nghiệp. Giữ nguyên API, dữ liệu và luồng nghiệp vụ hiện có; được phép tái bố trí giao diện và bổ sung các hỗ trợ UI/UX đã được duyệt.

Hướng hình ảnh: nền sáng trung tính, cấu trúc xanh đậm, xanh thương hiệu dùng có tiết chế, typography rõ cấp bậc, bề mặt phẳng với border nhẹ. Auth dùng bố cục split; workspace ưu tiên khả năng quét nhanh và giảm cuộn dài.

## Steps

1. Chuẩn hóa design tokens và component dùng chung trong `frontend/src/styles.css`; tạo toast, skeleton và hộp thoại xác nhận có accessible labels/focus states.
2. Nâng cấp Login/Signup thành split layout tiếng Việt; thêm hiện/ẩn mật khẩu, độ mạnh và checklist yêu cầu mật khẩu.
3. Tái bố trí `AppShell` thành workbench có topbar, sidebar startup thu gọn trên mobile và tabs Giai đoạn/Tài liệu/Trò chuyện giữ trạng thái hiện tại.
4. Việt hóa toàn bộ nội dung hiển thị, cải thiện loading/empty/error states và làm chat composer sticky.
5. Cập nhật unit tests cho hành vi mới và chạy typecheck, test, build; kiểm tra trực quan ở desktop 1440px, tablet 880px và mobile 375px.

## Completion criteria

- Không thay đổi endpoint, request/response hay quy tắc nghiệp vụ.
- Login/Signup, workspace, stage, documents và chat đều hiển thị tiếng Việt.
- Các UX đã duyệt hoạt động bằng chuột và bàn phím, có trạng thái focus rõ ràng.
- Không clipping, overlap hoặc horizontal scroll ngoài ý muốn tại 1440px, 880px và 375px.
- `npm run typecheck`, `npm test` và `npm run build` đều thành công.
