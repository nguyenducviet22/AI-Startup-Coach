# Startup List Scaling

## Overview

Giữ sidebar gọn khi có nhiều startup bằng cách cố định chiều cao theo viewport, chỉ cho danh sách cuộn, đồng thời thêm tìm kiếm, lọc trạng thái, đếm kết quả và hỗ trợ mobile panel.

## Steps

1. **Red:** thêm test component cho tìm kiếm không phân biệt hoa/thường/dấu, lọc đang làm/hoàn thành, số kết quả và empty state.
2. **Green:** tách toolbar/list trong `AppShell.tsx`, dùng state cục bộ; tự cuộn startup đang chọn vào vùng nhìn thấy và giữ thứ tự cập nhật gần nhất từ API.
3. **Responsive:** cập nhật `styles.css` để sidebar sticky có chiều cao viewport, header/form/toolbar cố định, list `overflow-y: auto`; mobile panel giới hạn `70dvh` và chỉ list cuộn.
4. **Refactor/verify:** thêm accessible labels, focus/scroll behavior; chạy test, typecheck/build và kiểm tra desktop/mobile.

## Completion criteria

- Số startup không làm tăng chiều cao trang.
- Tạo startup, tìm kiếm và filter luôn nhìn thấy; chỉ danh sách cuộn.
- Hiển thị `x/y startup`, empty state đúng ngữ cảnh và startup đang chọn tự vào viewport.
- Mobile panel không cao quá 70% viewport và tự đóng sau khi chọn.
- Frontend tests và build pass, không có overflow ngang hoặc lỗi console.
