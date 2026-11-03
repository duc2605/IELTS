# Word Runner IELTS · Desktop

Ứng dụng cửa sổ riêng để học 10.630 từ từ bốn quyển *English Vocabulary in Use*. Tàu ở bên trái, quái ở bên phải; gõ đúng từ để bắn. Không có game over. Có ba phần học, 10 màn, khoảng 100 đợt, ôn theo lịch, giới hạn học 30 phút mỗi ngày, xếp hạng, tạm dừng, tăng tốc và nghe lại Anh–Việt.

## Ubuntu 22.04.5

```bash
sudo apt update
sudo apt install python3-tk python3-venv ffmpeg speech-dispatcher
git clone https://github.com/duc2605/IELTS.git
cd IELTS
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./play-word-runner.sh
```

Ứng dụng mở trong một cửa sổ GUI; không mở trình duyệt và không cần đăng nhập. Nếu chưa có Internet hoặc chưa cài `edge-tts`, ứng dụng vẫn chạy và thử dùng giọng hệ thống qua `spd-say`. Giọng tự nhiên cần Internet để tạo âm thanh lần đầu; các từ đã phát được lưu lại trong bộ nhớ đệm để nghe tiếp khi ngoại tuyến.

Tiến độ được lưu tự động tại `~/.local/share/word-runner-ielts/state.json`. Bộ nhớ đệm âm thanh nằm cùng thư mục. Dùng **🇻🇳 Việt: Bật/Tắt** để bỏ phần đọc nghĩa tiếng Việt; **🔊 Âm thanh** tắt toàn bộ âm thanh.

## Windows

Máy cần Python 3 có Tkinter. Cài `edge-tts` và `ffmpeg` nếu muốn giọng tự nhiên, rồi chạy `python desktop.py`.

## Mã nguồn

- `desktop.py`: giao diện và luật chơi desktop.
- `data/words.json`: dữ liệu từ vựng.
- `play-word-runner.sh`: lệnh mở game trên Ubuntu.
- `requirements.txt`: giọng đọc tự nhiên tùy chọn.
