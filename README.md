# Word Runner IELTS

Game học từ vựng tiếng Anh từ bốn quyển *English Vocabulary in Use*. Có ba phần: nhìn và gõ lại, nhớ và viết, và ôn theo lịch. Game chạy trong trình duyệt, không cần tài khoản hay thư viện Python bổ sung.

## Chạy trên Ubuntu 22.04.5

Máy cần Python 3 và một trình duyệt web. Sau khi mã được đưa lên GitHub, chạy:

```bash
git clone https://github.com/duc2605/IELTS.git
cd IELTS
./play-word-runner.sh
```

Game sẽ mở tại `http://127.0.0.1:8765/`. Nếu trình duyệt không tự mở, hãy nhập địa chỉ được in trong Terminal. Giữ Terminal mở khi chơi; nhấn `Ctrl+C` để dừng. Nếu máy báo tập tin chưa có quyền thực thi, chạy `chmod +x play-word-runner.sh` một lần.

Tiến độ được lưu trong trình duyệt của máy đang chơi. Tiến độ trên Windows và Ubuntu không tự đồng bộ.

## Chạy trên Windows

Chạy `launcher.py` bằng Python 3.

## Cấu trúc

- `dist/`: trang web và dữ liệu từ vựng để chơi ngoại tuyến.
- `launcher.py`: máy chủ web cục bộ, chỉ lắng nghe trên `127.0.0.1`.
- `play-word-runner.sh`: lệnh mở game trên Ubuntu.
