# Word Runner IELTS · Desktop

Ứng dụng cửa sổ riêng để học 10.630 mục từ từ bốn quyển *English Vocabulary in Use*. Tàu ở bên trái, quái ở bên phải; gõ đúng từ để bắn. Không có game over. Mỗi quyển có đúng 20 màn; tất cả mục từ chưa học được chia vào 20 màn đó. Số đợt thay đổi theo tốc độ gõ; từ chưa gõ kịp sẽ trở lại hàng chờ và màn chỉ kết thúc khi gõ đủ từ. Có ba phần học, ôn theo lịch, giới hạn học 30 phút mỗi ngày, xếp hạng, tạm dừng, tăng tốc và nghe lại Anh–Việt.

Sau mỗi đợt, game dừng ở bảng ôn nhanh ngay trong cửa sổ chơi, với từ tiếng Anh, nghĩa tiếng Việt và nút 🔊 cho từng từ. Nhấn **Enter** hoặc bấm **Tiếp tục** để đóng bảng và bắt đầu đợt sau. Từ chưa gõ kịp có dấu ↻ và sẽ xuất hiện lại.

Mỗi màn là một nhóm bài học theo mục lục của quyển sách. Trong màn, từ ngắn xuất hiện trước, từ dài xuất hiện sau. Mỗi màn có tối đa 20 đợt; đợt cuối không giới hạn thời gian để bạn gõ nốt các từ còn lại mà không mất từ. Nhãn chủ đề và phân nhóm được tạo từ các PDF gốc bằng `build_topics.py` và lưu trong `data/topics.json`.

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

Khi cập nhật từ bản chia màn theo số lượng từ sang bản chia theo chủ đề, danh sách từ đã học được giữ nguyên và game bắt đầu rà lại từ chủ đề đầu tiên để không bỏ sót từ chưa học. Chủ đề đã học hết sẽ được tự động bỏ qua.

## Windows

Máy cần Python 3 có Tkinter. Cài `edge-tts` và `ffmpeg` nếu muốn giọng tự nhiên, rồi chạy `python desktop.py`.

## Mã nguồn

- `desktop.py`: giao diện và luật chơi desktop.
- `data/words.json`: dữ liệu từ vựng.
- `play-word-runner.sh`: lệnh mở game trên Ubuntu.
- `requirements.txt`: giọng đọc tự nhiên tùy chọn.
