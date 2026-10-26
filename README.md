# Director: tool edit video bằng AI

Đưa vào **một file video** (có sẵn sub hoặc không), gõ một câu mô tả phong cách nếu muốn. Tool tự lo phần còn lại: hiểu câu chuyện, cắt gọn, dựng hook, thêm phụ đề, hiệu ứng, tiếng động, nhạc, đổi khung hình, rồi xuất video thành phẩm.

```
director edit tap12.mp4
director edit tap12.mp4 -c "drama dọc 9:16, hook bằng cú twist, 60 giây, phụ đề vàng to"
director edit tap12.mp4 -c "cả TikTok lẫn YouTube, nhiều hiệu ứng" --variants 3
director revise outputs/jobs/tap12_xxxx/tap12.plan.json "intro nhanh hơn, bỏ đoạn 0:40"
director studio            # giao diện web tại http://127.0.0.1:7860
```

- Bản thiết kế: [docs/DESIGN.md](docs/DESIGN.md)
- Thư viện hiệu ứng: [docs/EFFECTS.md](docs/EFFECTS.md)

---

## Tool làm được gì

| Bước | Tool tự làm |
|---|---|
| Hiểu video | Nhận thể loại (hoạt hình / người thật), chép lời (Whisper) hoặc đọc sub có sẵn trên hình (OCR), tách thoại khỏi nhạc (Demucs), dò mặt nhân vật (có model riêng cho mặt hoạt hình), gom nhóm nhân vật, đoán cảm xúc từng câu, tìm highlight, chuyển cảnh, beat nhạc, điểm âm thanh bùng nổ |
| Hiểu lệnh | Đọc lệnh tiếng Việt tự do: khung hình, thời lượng, số phần, kiểu hook, kiểu phụ đề, màu, nhịp, mật độ hiệu ứng, nhạc... |
| Lập kế hoạch | Cắt khoảng lặng, từ đệm ("ừm", "à"), câu nói hỏng (giữ lần nói sau); chọn hook (twist trước rồi tua ngược "Trước đó..."); nén theo thời lượng; chia phần có cliffhanger; gắn hiệu ứng theo cảm xúc với quy tắc chống lạm dụng |
| Khung hình | Mọi tỉ lệ theo lệnh (9:16, 16:9, 4:5, 1:1, 21:9, điện ảnh, 1080x1350...), nhiều khung một lúc; bám mặt nhân vật; **có sẵn sub thì giữ trọn khung + nền mờ để không mất chữ** |
| Hiệu ứng | Gần 200 mục: chuyển cảnh, camera, tốc độ, 15 kiểu phụ đề, chữ/tiêu đề, hiệu ứng manga (đường tập trung, gân giận, mồ hôi...), màu, phong cách hình, hạt, bố cục, âm thanh, 12 combo theo cảm xúc |
| Âm thanh | 48 tiếng động tự tổng hợp (không lo bản quyền), nhạc nền tự giảm khi có thoại, tắt nhạc trước câu sốc, chuẩn âm lượng -14 LUFS |
| Claude (tuỳ chọn) | Đọc lời thoại + xem khung hình để hiểu câu chuyện, tên nhân vật; lập kế hoạch dựng; **tự xem bản nháp, chấm điểm, sửa** (2 vòng); sửa bằng lời nói |
| Xuất | MP4 cho từng khung, file EDL/OTIO để mở trong DaVinci Resolve / Premiere chỉnh tiếp |
| Ghi nhớ | Nhận ra bộ phim đã dựng trước đây: dùng lại tên & màu nhân vật, phong cách; ghi nhớ các yêu cầu sửa của bạn |

Không có API Claude, tool vẫn chạy đầy đủ bằng bộ lập kế hoạch offline.

---

## Cài đặt (Windows, GTX 1080)

### 1. Phần bắt buộc

1. **Python 3.11** (tích "Add to PATH" khi cài): https://www.python.org/downloads/
2. **Node.js 20 LTS**: https://nodejs.org/
3. **ffmpeg** (bản có NVENC, ví dụ bản "full" của gyan.dev): giải nén rồi thêm thư mục `bin` vào PATH.
4. Tải code và cài:

```powershell
git clone https://github.com/phamvanson12398/editvideo.git
cd editvideo
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[asr,ocr,studio,export]"
cd remotion
npm install
cd ..
director doctor
```

`director doctor` kiểm tra từng thành phần và chỉ ra cái nào còn thiếu.

### 2. Chép lời bằng GPU (khuyên dùng)

`faster-whisper` dùng CUDA qua CTranslate2. Với GTX 1080 (kiến trúc Pascal), tool tự chọn `int8` vì FP16 trên Pascal rất chậm. Cần cài **CUDA 12 + cuDNN 9** của NVIDIA (hoặc `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`). Nếu không có GPU, Whisper chạy bằng CPU với model `small`.

Đổi model: `--whisper-model large-v3-turbo` (mặc định khi có GPU), `medium`, `small`.

### 3. Tách thoại khỏi nhạc (tuỳ chọn, giúp chép lời chuẩn hơn và mix lại nhạc gốc)

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu126
pip install -e ".[separation]"
```

> **Lưu ý GTX 10xx:** CUDA 13 đã bỏ hỗ trợ Pascal và một số bản PyTorch mới cũng bỏ `sm_61`. Hãy dùng bản `cu126` như lệnh trên. Kiểm tra bằng `director doctor` (dòng PyTorch CUDA phải có `sm_61` hoặc `sm_60`).

### 4. Nâng nét và slow motion bằng GPU (tuỳ chọn)

Tải hai công cụ chạy bằng Vulkan (không cần CUDA, chạy tốt trên GTX 1080), giải nén vào `assets/bin/`:

- Real-ESRGAN ncnn Vulkan: https://github.com/xinntao/Real-ESRGAN/releases (dùng model `realesr-animevideov3` cho hoạt hình)
- RIFE ncnn Vulkan: https://github.com/nihui/rife-ncnn-vulkan/releases

Khi có RIFE, hiệu ứng làm chậm cho video người thật dùng nội suy khung mượt. Thêm `--upscale` để nâng nét x2 trước khi dựng (hợp khi video gốc 720p mà cần cắt khung dọc).

### 5. Claude (tuỳ chọn, để tool "thông minh" nhất)

Đặt biến môi trường `ANTHROPIC_API_KEY` (hoặc đăng nhập bằng `ant auth login`). Mặc định dùng model `claude-opus-5-5`; đổi bằng biến `DIRECTOR_MODEL`. Tắt Claude cho một lần chạy: `--no-llm`.

### 6. Nhận diện người nói (tuỳ chọn)

`pip install -e ".[diarize]"` và đặt `HF_TOKEN` (token Hugging Face đã chấp nhận điều khoản của `pyannote/speaker-diarization-3.1`).

---

## Cách dùng

### Lệnh `edit`

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `-c "..."` | Mô tả phong cách bằng lời (tiếng Việt thoải mái) |
| `-f 9:16 -f youtube` | Khung hình (lặp lại để xuất nhiều khung). Không ghi = theo lệnh, hoặc giữ khung gốc |
| `--preset anime-drama` | Chọn preset (xem `director styles`) |
| `--variants 3` | Xuất 3 phương án: chuẩn / mạnh tay / an toàn |
| `--draft` | Bản nháp nhanh để xem trước |
| `--critic 2` | Số vòng tự xem lại và sửa (cần Claude) |
| `--genre anime` | Ghi đè thể loại nếu tool nhận sai |
| `--upscale` | Nâng nét x2 bằng Real-ESRGAN |
| `--no-llm` | Không dùng Claude |
| `-o outputs` | Thư mục kết quả |

Kết quả nằm trong `outputs/`: `<tên>_<khung>.mp4`, `<tên>.edl`, `<tên>.otio`. Thư mục `outputs/jobs/<tên>_xxxx/` chứa phân tích (`index.json`), kế hoạch dựng (`*.plan.json`), phong cách (`style.json`) và nhận xét của vòng tự xem lại.

### Ví dụ lệnh phong cách

- `drama dọc 9:16, hook bằng cú twist, 60 giây` → hook là câu twist, tua VHS về đầu, nén còn 60 giây
- `chia 3 phần, mỗi phần kết bằng cliffhanger` → 3 video, có "Còn tiếp..."
- `tối giản, màu ấm, không tiếng động` → chỉ cắt gọn và chỉnh màu
- `nhiều hiệu ứng, phụ đề karaoke vàng, thanh tiến trình` → mật độ hiệu ứng cao
- `thêm phụ đề to kiểu TikTok dù đã có sub` → vẫn thêm phụ đề khi video có sub sẵn
- `khung instagram và vuông` → xuất 4:5 và 1:1
- `nhạc buồn, giữ nguyên nhạc gốc` → chọn nhạc trong `assets/music/sad/`

### Sửa bằng lời

```
director revise outputs/jobs/tap12_xxxx/tap12.plan.json "intro nhanh hơn"
director revise outputs/jobs/tap12_xxxx/tap12.plan.json "bỏ đoạn 0:40, tiêu đề là: Bí mật động trời"
```

Có Claude thì sửa được mọi kiểu yêu cầu. Không có Claude thì hiểu được các yêu cầu về phong cách, khung hình, nhịp, bỏ đoạn theo thời điểm, đổi tiêu đề. Bản cũ được lưu trong `history/`.

### Tài nguyên của bạn

| Thư mục | Đặt vào | Tool dùng thế nào |
|---|---|---|
| `assets/music/<tâm trạng>/` | Nhạc nền (`sad`, `happy`, `tense`, `epic`, `romance`, `comedy`) | Chọn theo lệnh hoặc theo cảm xúc cảnh |
| `assets/sfx/` | Tiếng động `<id>.wav` (vd `slap.wav`, `dun_dun_dun.mp3`) | Thay tiếng động tổng hợp cùng tên |
| `assets/luts/` | File `.cube` | Dùng bằng tên file trong lệnh/preset |
| `assets/bin/` | Real-ESRGAN, RIFE | Nâng nét, slow motion bằng GPU |

Hãy chỉ dùng nhạc và tiếng động bạn có quyền sử dụng.

---

## Kiến trúc mã nguồn

```
director/
  perception/   phân tích video: âm thanh, cảnh, hình ảnh (thể loại, mặt, nhân vật, sub có sẵn), lời thoại, ngữ nghĩa
  style/        Style DNA, preset, hiểu lệnh tiếng Việt
  effects/      thư viện hiệu ứng (catalog), combo, quy tắc dùng hiệu ứng
  agent/        planner offline, Claude (hiểu truyện, lập kế hoạch, sửa), vòng tự xem lại
  plan/         schema kế hoạch dựng, khung hình, compiler (draft theo thời gian gốc → timeline)
  render/       chuẩn bị clip (ffmpeg), trộn âm thanh, gọi Remotion, tiếng động tổng hợp, LUT
  aiops/        Real-ESRGAN / RIFE (Vulkan)
  export/       EDL, OTIO
  memory/       nhớ bộ phim & sở thích (SQLite, ~/.director/memory.db)
  studio/       giao diện web
remotion/       lớp hình ảnh: đổi khung, camera, chuyển cảnh, phụ đề, chữ, manga, hạt, phong cách
assets/         font tiếng Việt (OFL), model dò mặt hoạt hình (MIT), nơi đặt nhạc/sfx/LUT của bạn
tests/          test tự động + script tạo video mẫu
```

Chạy test: `pip install -e ".[dev]"` rồi `pytest`.

## Giấy phép tài nguyên đi kèm

- Font (Be Vietnam Pro, Montserrat, Oswald, Lexend, Baloo 2, Roboto): SIL Open Font License, xem `assets/fonts/OFL-*.txt`.
- `assets/models/lbpcascade_animeface.xml`: MIT © nagadomi.
- Tiếng động và LUT: tạo bằng code trong repo.
- Remotion: miễn phí cho cá nhân và công ty tối đa 3 người; lớn hơn cần mua license tại remotion.dev.
