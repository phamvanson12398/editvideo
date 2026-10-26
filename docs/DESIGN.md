# Director — Tool edit video bằng AI

> Đầu vào: video gốc + mô tả phong cách (bằng lời, hoặc một video mẫu "edit giống thế này").
> Đầu ra: video thành phẩm, kèm vài phiên bản và file timeline để chỉnh tay.

---

## 1. Điểm khác biệt so với các tool hiện nay

Hầu hết tool "AI edit" hiện nay chạy **một lượt**: phân tích → áp template → xuất file. Director làm việc như một **đạo diễn dựng phim**:

| # | Tính năng | Ý nghĩa |
|---|---|---|
| 1 | **Tự xem lại và tự sửa** (Critic Loop) | Sau khi dựng bản nháp, một AI "xem" bản nháp, chấm điểm theo yêu cầu phong cách, chỉ ra lỗi (cắt hụt, phụ đề che mặt, nhịp chậm...) rồi sửa. Lặp 2–3 vòng trước khi xuất bản cuối. |
| 2 | **Style DNA**: học phong cách từ video mẫu | Đưa vào một video bạn thích, tool đo nhịp cắt, kiểu phụ đề, màu, tần suất zoom, cách dùng tiếng động... rồi lưu thành hồ sơ phong cách dùng lại được. |
| 3 | **Hiểu nội dung, không chỉ hiểu thời gian** | Tool biết câu nào là hook, câu nào là cao trào, chỗ nào người nói nói hỏng rồi nói lại (giữ lần nói hay nhất), câu nào nên nhấn bằng zoom. |
| 4 | **Sửa bằng hội thoại** | "Đoạn mở đầu nhanh hơn", "bỏ phụ đề ở đoạn 0:40". Tool chỉ sửa phần liên quan trong kế hoạch dựng, không dựng lại từ đầu. |
| 5 | **Nhiều phiên bản cùng lúc** | Xuất 3 phương án (an toàn / mạnh tay / thử nghiệm) từ một kế hoạch. |
| 5b | **Khung hình tuỳ theo lệnh** | Khung nào cũng được: "TikTok", "khung Instagram", "điện ảnh", "4:5", "1080x1350", hoặc nhiều khung một lúc. Không nói gì thì giữ khung gốc. Xem mục 3 "Khung hình linh hoạt". |
| 6 | **Tối ưu giữ chân người xem** | Chấm điểm hook 3 giây đầu, phát hiện đoạn dễ khiến người xem lướt qua (im lặng dài, hình tĩnh lâu, lặp ý) và xử lý. |
| 7 | **Học thói quen của bạn** | Mỗi lần bạn sửa tay hoặc chọn phương án nào, tool ghi nhớ để lần sau dựng sát ý bạn hơn. |
| 8 | **Không khoá bạn trong tool** | Xuất timeline OpenTimelineIO (FCPXML/EDL) để mở trong DaVinci Resolve / Premiere và chỉnh tiếp. |

---

## 2. Kiến trúc tổng thể

```
                    ┌──────────────────────────────────────────────┐
  Video gốc ──────► │ ① PERCEPTION (chạy trên máy, GTX 1080)       │
  Video mẫu ──┐     │  lời nói · cảnh · mặt · cảm xúc · âm thanh   │
              │     └───────────────┬──────────────────────────────┘
              │                     ▼
              │            ┌──────────────────┐
              │            │ ② VIDEO INDEX    │  (JSON + SQLite + ảnh keyframe)
              │            └────────┬─────────┘
              ▼                     │
   ┌────────────────────┐           │
   │ ③ STYLE DNA        │◄── mô tả bằng lời / hồ sơ đã lưu / sở thích đã học
   └─────────┬──────────┘           │
             └──────────┬───────────┘
                        ▼
            ┌──────────────────────────┐        ┌───────────────────────┐
            │ ④ DIRECTOR AGENT (LLM)   │◄──────►│ ⑤ EFFECT REGISTRY     │
            │  lên Edit Plan (JSON)    │        │  danh sách hiệu ứng   │
            └───────────┬──────────────┘        │  tool làm được        │
                        ▼                       └───────────────────────┘
            ┌──────────────────────────┐
            │ ⑥ RENDER ENGINE          │  bản nháp 480p nhanh → bản cuối 1080p/4K
            │  ffmpeg + AI ops + Remotion (lớp phủ)                    │
            └───────────┬──────────────┘
                        ▼
            ┌──────────────────────────┐   chưa đạt
            │ ⑦ CRITIC (VLM xem nháp)  │──────────────► quay lại ④ kèm danh sách lỗi
            └───────────┬──────────────┘
                        │ đạt (hoặc hết số vòng)
                        ▼
            ┌──────────────────────────┐
            │ ⑧ STUDIO (web UI)        │  xem trước, sửa bằng chat/timeline,
            │  xuất MP4 + OTIO         │  chọn phương án, ghi nhận sở thích
            └──────────────────────────┘
```

Nguyên tắc thiết kế:

- **LLM không đụng vào pixel.** LLM chỉ viết Edit Plan (JSON có schema). Mọi thao tác thật do code đã kiểm thử thực hiện, nên kết quả ổn định và có thể tái lập.
- **Edit Plan là trung tâm.** Bản nháp, bản cuối, các phiên bản, timeline OTIO và mọi lần sửa bằng chat đều là các phép biến đổi trên cùng một Edit Plan.
- **Tách lớp khi render.** ffmpeg xử lý video gốc (nhanh, encode bằng NVENC). Remotion chỉ vẽ lớp phủ trong suốt. Sau đó ghép lại.
- **Local trước, cloud khi cần.** Phần "nhìn và nghe" chạy trên GTX 1080. Phần "suy nghĩ" (lập kế hoạch, phê bình) dùng LLM trên cloud vì máy không đủ sức chạy model lớn.

---

## 3. Chi tiết từng module

### ① Perception: tool "nhìn và nghe" video

| Tín hiệu | Công cụ | Dùng để |
|---|---|---|
| Lời nói + thời gian từng từ | **faster-whisper / WhisperX** (large-v3-turbo) | Phụ đề, cắt theo câu, tìm hook |
| Từ đệm ("ừm", "à", "kiểu là") | Từ điển + timestamp của WhisperX | Tự cắt từ thừa |
| Nói hỏng rồi nói lại | So sánh độ giống câu liên tiếp (embedding văn bản) | Giữ lần nói hay nhất |
| Ngữ điệu (to/nhỏ, cao/thấp) | **librosa** / **parselmouth** | Zoom vào từ được nhấn mạnh |
| Chuyển cảnh | **PySceneDetect** / **TransNetV2** | Cắt đúng điểm cảnh |
| Mặt, tư thế, vị trí người | **MediaPipe**, **YOLO11** | Reframe theo khung đích, bám theo người, tránh phụ đề che mặt |
| Cảm xúc khuôn mặt | Model nhận diện cảm xúc nhẹ trên mặt đã cắt | Chọn khoảnh khắc biểu cảm |
| Năng lượng âm thanh, beat nhạc | **librosa** (onset, beat tracking) | Cắt theo nhịp, tìm cao trào |
| Ý nghĩa hình ảnh | **SigLIP / CLIP** embedding mỗi keyframe | Tìm cảnh bằng câu chữ ("đoạn cầm điện thoại") |
| Chất lượng hình | Độ nét (Laplacian), rung, thiếu sáng | Loại cảnh hỏng |
| Hiểu toàn cục (tuỳ chọn, cloud) | **Gemini** nhận cả video | Tóm tắt, cấu trúc câu chuyện, highlight |

### ② Video Index

Toàn bộ kết quả trên được lưu vào một "bản đồ video" theo dòng thời gian:

```jsonc
{
  "source": { "path": "input.mp4", "duration": 312.4, "fps": 30, "size": [1920, 1080] },
  "words":   [{ "t0": 1.20, "t1": 1.48, "text": "Hôm", "emphasis": 0.2 }, ...],
  "sentences": [{ "id": "s12", "t0": 40.1, "t1": 44.9, "text": "...", "role": "hook", "retake_of": null }],
  "scenes":  [{ "t0": 0, "t1": 12.3, "quality": 0.9, "tags": ["indoor", "talking-head"] }],
  "faces":   [{ "t": 1.0, "boxes": [[0.41, 0.18, 0.22, 0.39]], "emotion": "happy" }],
  "audio":   { "beats": [...], "energy": [...], "silences": [[5.1, 6.3], ...] },
  "highlights": [{ "t0": 88.0, "t1": 97.5, "score": 0.93, "reason": "cao trào, cười lớn" }]
}
```

Keyframe và embedding lưu trong SQLite (bảng vector với `sqlite-vec`) để Director Agent tìm kiếm được.

### ③ Style DNA: mô tả phong cách có cấu trúc

Mọi phong cách, dù đến từ câu chữ, video mẫu hay hồ sơ đã lưu, đều được quy về cùng một cấu trúc:

```jsonc
{
  "name": "tiktok-nang-dong",
  "pacing":      { "avg_shot_sec": 1.8, "remove_silence_over": 0.25, "cut_on_beat": true },
  "hook":        { "max_sec": 3, "strategy": "start-with-punchline" },
  "captions":    { "preset": "word-pop", "font": "Be Vietnam Pro", "weight": 900,
                   "color": "#FFFFFF", "highlight": "#FFD400", "position": "lower-third-safe",
                   "words_per_line": 3 },
  "camera":      { "punch_in_on_emphasis": true, "zoom_range": [1.0, 1.35], "reframe": "follow-face" },
  "transitions": { "default": "hard-cut", "accent": ["whip", "zoom-blur"], "frequency": "low" },
  "color":       { "lut": "warm-pop.cube", "intensity": 0.7 },
  "audio":       { "music_mood": "upbeat", "duck_db": -14, "sfx": ["whoosh", "pop"], "loudness_lufs": -14 },
  "broll":       { "enabled": true, "density": "medium", "source": ["pexels", "local"] },
  "frames":      null   // null = lấy từ lệnh của người dùng, không có thì giữ khung gốc
}
```

**Trích Style DNA từ video mẫu:** chạy Perception trên video mẫu rồi đo các chỉ số. Độ dài shot trung bình lấy từ chuyển cảnh, tần suất zoom lấy từ biến thiên khung hình, màu chủ đạo lấy từ histogram (sinh LUT xấp xỉ bằng color transfer). Kiểu phụ đề được nhận diện bằng VLM (gửi vài khung hình cho Claude/Gemini mô tả font, màu, vị trí, hiệu ứng).

### ④ Director Agent: bộ não

Agent dùng **tool use** chứ không trả về một lần:

```
tools:
  search_index(query)        → tìm câu/cảnh theo nghĩa
  get_transcript(t0, t1)
  get_keyframes(t0, t1)      → ảnh để LLM nhìn
  list_effects()             → đọc Effect Registry
  find_broll(keywords)       → Pexels/Pixabay/thư mục local
  find_music(mood, bpm)
  submit_plan(plan)          → kiểm tra schema; sai thì trả lỗi cho agent tự sửa
```

Quy trình suy nghĩ:

1. **Cấu trúc câu chuyện:** hook → bối cảnh → nội dung chính → cao trào → kêu gọi hành động.
2. **Chọn và sắp đoạn**, bỏ phần thừa, giữ lần nói hay nhất.
3. **Gắn hiệu ứng** theo Style DNA, chỉ dùng hiệu ứng có trong Registry.
4. **Ước lượng độ giữ chân**, chỉnh lại hook nếu yếu.

**Edit Plan** (rút gọn):

```jsonc
{
  "version": 3,
  "outputs": [   // một Edit Plan, nhiều khung; mỗi khung có reframe/bố cục riêng
    { "id": "tiktok", "aspect": "9:16", "size": [1080, 1920], "fps": 30, "safe_zone": "tiktok" },
    { "id": "feed",   "aspect": "4:5",  "size": [1080, 1350], "fps": 30, "safe_zone": "instagram" }
  ],
  "tracks": {
    "video": [
      { "id": "c1", "src": "input.mp4", "in": 88.0, "out": 91.2,
        "reframe": { "default": "follow-face", "per_output": { "feed": "fit-blur" } },
        "ops": [{ "type": "punch_in", "at": 0.6, "scale": 1.25, "ease": "spring" }] },
      { "id": "c2", "src": "broll/pexels_123.mp4", "in": 0, "out": 1.5, "role": "broll" }
    ],
    "overlay": [
      { "type": "captions", "preset": "word-pop", "from": 0, "to": 58.4 },
      { "type": "title", "text": "3 SAI LẦM", "from": 0.2, "to": 2.0, "preset": "slam" }
    ],
    "audio": [
      { "type": "voice", "src": "input.mp4", "denoise": true },
      { "type": "music", "src": "music/upbeat_02.mp3", "duck_under": "voice", "duck_db": -14 },
      { "type": "sfx", "src": "sfx/whoosh.wav", "at": 3.2 }
    ]
  },
  "color": { "lut": "warm-pop.cube", "intensity": 0.7 },
  "notes": "Mở bằng câu cao trào ở 1:28 để làm hook."
}
```

Schema định nghĩa bằng **Pydantic** (Python), xuất JSON Schema, sinh type **zod/TypeScript** cho Remotion. Một nguồn sự thật cho cả hai phía.

### Khung hình linh hoạt (theo lệnh)

Khung hình không cố định. Người dùng ra lệnh thế nào thì tool dựng theo khung đó.

**Hiểu lệnh về khung.** Director Agent chuyển câu chữ thành danh sách `outputs`:

| Người dùng nói | Khung | Kích thước mặc định |
|---|---|---|
| "TikTok", "Reels", "Shorts", "video dọc" | 9:16 | 1080×1920 |
| "YouTube", "video ngang" | 16:9 | 1920×1080 (hoặc 3840×2160 nếu nói "4K") |
| "Instagram feed", "khung bài đăng" | 4:5 | 1080×1350 |
| "vuông", "Facebook feed" | 1:1 | 1080×1080 |
| "điện ảnh", "cinematic" | 2.39:1 | 1920×804, hoặc 16:9 có viền đen nếu cần đăng nền tảng |
| "21:9", "ultrawide" | 21:9 | 2560×1080 |
| "3:4", "2:3", "5:4"... | đúng tỉ lệ đó | cạnh dài 1920 |
| "1080x1350", "720p dọc" | đúng kích thước đó | |
| "cả TikTok lẫn YouTube" | nhiều khung | mỗi khung một file |
| không nói gì | giữ khung gốc | giữ kích thước gốc |

Kích thước luôn được làm tròn về số chẵn (yêu cầu của H.264/HEVC). Tỉ lệ lạ vẫn được chấp nhận, kèm cảnh báo nếu nền tảng đích không hỗ trợ.

**Cách đưa video gốc vào khung đích** (`reframe`), chọn theo lệnh hoặc để agent tự chọn theo nội dung từng đoạn:

| Chế độ | Làm gì | Hợp với |
|---|---|---|
| `follow-face` | Cắt khung bám theo mặt người nói, chuyển động mượt (lọc Kalman / làm mượt quỹ đạo) | Video nói chuyện |
| `follow-subject` | Bám theo vật thể/người chuyển động (YOLO + tracking) | Thể thao, hành động, thú cưng |
| `speaker-switch` | Có 2–3 người thì nhảy khung sang người đang nói | Podcast, phỏng vấn |
| `split` | Chia khung trên/dưới hoặc trái/phải, mỗi người một ô | Podcast 2 người trong khung dọc |
| `fit-blur` | Giữ nguyên hình, phần thừa lấp bằng chính video làm mờ | Cảnh rộng không nên cắt |
| `fit-pad` | Giữ nguyên hình, thêm viền màu hoặc nền thiết kế | Phong cách tối giản, có chữ ở viền |
| `letterbox` | Thêm viền đen trên dưới | Phong cách điện ảnh |
| `center` / `manual` | Cắt giữa, hoặc theo toạ độ người dùng chỉ định | Khi cần kiểm soát tay |

Mỗi clip có thể dùng chế độ khác nhau, và mỗi khung đầu ra có thể ghi đè (`per_output`). Ví dụ cùng một cảnh: bản 9:16 dùng `follow-face`, bản 4:5 dùng `fit-blur`.

**Bố cục tự thích ứng.** Lớp phủ Remotion không dùng toạ độ pixel cố định mà dùng **bố cục theo vùng** (top / center / lower-third...) tính theo khung đích:

- Mỗi nền tảng có **vùng an toàn** riêng (TikTok có nút bấm bên phải và chú thích phía dưới; Shorts, Reels khác một chút). Phụ đề và chữ luôn nằm trong vùng an toàn.
- Cỡ chữ và số từ mỗi dòng phụ đề tự co giãn theo chiều rộng khung: khung dọc ít chữ hơn, chữ to hơn; khung ngang nhiều chữ hơn một dòng.
- Phụ đề tự né mặt người (dùng vị trí mặt từ Perception).
- Critic kiểm tra riêng từng khung đầu ra.

**Render nhiều khung.** Phần dùng chung (khử ồn, mix âm thanh, AI ops, LUT) chỉ xử lý một lần. Chỉ bước reframe và lớp phủ chạy riêng cho từng khung.

### ⑤ Effect Registry: thư viện hiệu ứng dạng plugin

Mỗi hiệu ứng là một plugin có manifest để agent biết dùng thế nào:

```yaml
id: punch_in
engine: remotion          # remotion | ffmpeg | ai
description: Zoom nhanh vào chủ thể khi nhấn mạnh
params:
  scale: { type: number, min: 1.0, max: 1.6, default: 1.2 }
  ease:  { enum: [spring, linear, ease-out] }
cost: low                 # agent cân nhắc thời gian render
gpu: false
```

Ba loại hiệu ứng:

- **remotion**: phụ đề động, tiêu đề, sticker, progress bar, khung, emoji, chuyển cảnh đồ hoạ.
- **ffmpeg**: cắt, ghép, reframe, LUT, tốc độ, ổn định hình (vidstab), khử ồn, loudnorm.
- **ai**: tách nền, xoá vật thể, nâng nét, slow motion, khử ồn bằng AI.

Thêm hiệu ứng mới chỉ cần thêm plugin, không phải sửa agent.

### ⑥ Render Engine

```
Edit Plan
  ├─► AI ops (chỉ các đoạn cần, có cache theo hash) ──► clip đã xử lý
  ├─► ffmpeg: cắt + LUT + speed (chung) → reframe riêng từng khung ──► base_<khung>.mp4 (NVENC)
  ├─► Remotion: lớp phủ trong suốt cho từng khung ──► overlay.mov (ProRes 4444) / .webm (VP9 alpha)
  ├─► audio mix: voice + music (ducking) + sfx ──► mix.wav (loudnorm)
  └─► ffmpeg overlay + mux ──► final_<khung>.mp4 (mỗi khung một file)
```

- **Bản nháp:** 480p, preset nhanh, bỏ AI ops nặng (dùng bản xấp xỉ). Mục tiêu dưới 1 phút cho video 1 phút.
- **Bản cuối:** độ phân giải đầy đủ, mọi AI ops.
- **Cache theo nội dung:** đoạn nào không đổi giữa các lần sửa thì không render lại. Sửa bằng chat vì thế rất nhanh.

### ⑦ Critic Loop: tự xem và tự sửa

1. Lấy mẫu khung hình từ bản nháp (khoảng 1 khung/giây, dày hơn quanh điểm cắt) kèm transcript và Edit Plan.
2. Gửi cho VLM (Claude hoặc Gemini; Gemini xem được cả file video) với bảng chấm điểm:
   - Bám sát Style DNA không?
   - Hook 3 giây đầu có đủ mạnh không?
   - Có cắt giữa từ, giật hình, phụ đề che mặt, phụ đề sai chính tả không?
   - Nhịp có đều không, có đoạn nào chán không?
3. Critic trả về JSON: điểm từng tiêu chí và danh sách lỗi kèm thời điểm.
4. Có lỗi thì gửi lại cho Director Agent sửa Edit Plan, rồi render lại phần bị ảnh hưởng.
5. Dừng khi đạt ngưỡng điểm hoặc sau tối đa 3 vòng (giới hạn chi phí API).

Kèm theo là các **kiểm tra tự động không cần AI**: phụ đề vượt vùng an toàn của TikTok/Shorts, âm lượng lệch chuẩn LUFS, khung đen, đoạn quá ngắn dưới 0,3 giây.

### ⑧ Studio: giao diện web

- **Next.js + @remotion/player:** xem trước ngay trên trình duyệt.
- Khung chat để sửa ("làm intro nhanh hơn"). Mỗi lần sửa tạo một phiên bản Edit Plan mới, có diff và undo.
- Timeline đơn giản: kéo đầu/cuối clip, bật/tắt hiệu ứng, sửa chữ phụ đề.
- So sánh các phương án cạnh nhau, chọn một bản. Lựa chọn được ghi vào **bộ nhớ sở thích**.
- Thư viện Style DNA: lưu, nhân bản, chỉnh, chia sẻ.

---

## 4. Chạy trên GTX 1080 (8 GB VRAM)

GTX 1080 dùng kiến trúc Pascal (compute 6.1). Những điều cần biết:

- **FP16 trên Pascal rất chậm** vì không có Tensor Core. Model nên chạy **FP32 hoặc INT8**.
- **Cài PyTorch bản build CUDA 12.x** (ví dụ `cu126`). CUDA 13 đã bỏ hỗ trợ Pascal, và một số bản build PyTorch mới cũng bỏ sm_61. Kiểm tra sau khi cài: `torch.cuda.get_arch_list()` phải có `sm_61`.
- **NVENC** encode H.264/HEVC tốt, nhưng không encode AV1.
- **Mỗi lúc chỉ chạy một model GPU.** Render Engine dùng hàng đợi GPU: nạp model, xử lý, giải phóng VRAM rồi mới chuyển sang model tiếp theo.

| Tác vụ | Model | Chạy ở đâu | Ghi chú cho 1080 |
|---|---|---|---|
| Nhận dạng giọng nói | faster-whisper large-v3-turbo | Local | `compute_type="int8"` hoặc `float32`, khoảng 3–5 GB |
| Dò mặt / vật thể | MediaPipe, YOLO11n/s | Local | Nhẹ, chạy nhanh |
| Embedding hình | SigLIP base | Local | Nhẹ |
| Chuyển cảnh | TransNetV2 | Local | Nhẹ |
| Tách nền người | RobustVideoMatting | Local | Chạy tốt ở 1080p |
| Phân đoạn vật thể | SAM 2 (tiny/small) | Local | Bản large dễ hết VRAM |
| Xoá vật thể | ProPainter | Local, giới hạn | Xử lý vùng cắt ở 720p, đoạn ngắn |
| Nâng nét | Real-ESRGAN | Local | Chậm, chỉ dùng cho đoạn cần |
| Slow motion | RIFE (Practical-RIFE) | Local | Chạy tốt |
| Khử ồn | DeepFilterNet | Local | Chạy được cả trên CPU |
| Tách giọng / nhạc | Demucs (htdemucs) | Local | Khoảng 4 GB, chạy theo đoạn |
| Lập kế hoạch dựng | Claude (Opus cho kế hoạch, Sonnet cho sửa nhanh) | Cloud | Model đủ mạnh để suy nghĩ không chạy nổi trên 8 GB |
| Phê bình bản nháp | Claude (ảnh) / Gemini (video) | Cloud | |
| Hiểu toàn bộ video | Gemini | Cloud, tuỳ chọn | |
| B-roll / nhạc / SFX | Pexels, Pixabay API, thư viện local | Cloud/local | |

Chi phí API được kiểm soát bằng: gửi keyframe thay vì cả video, cache kết quả theo hash, giới hạn số vòng Critic, và tuỳ chọn tắt hẳn Critic.

---

## 5. Công nghệ và cấu trúc repo

- **Python 3.11**: pipeline, Perception, Agent, Render orchestration (FastAPI làm API, quản lý gói bằng `uv`).
- **TypeScript**: Remotion (lớp phủ) và Studio (Next.js).
- **ffmpeg** bản có NVENC.
- **SQLite + sqlite-vec**: Video Index, phiên bản Edit Plan, bộ nhớ sở thích.
- **OpenTimelineIO**: xuất timeline.

```
editvideo/
├── docs/DESIGN.md
├── director/                  # Python package
│   ├── perception/            # whisper, scenes, faces, audio, embeddings
│   ├── index/                 # Video Index + truy vấn
│   ├── style/                 # Style DNA: parse lời, trích từ video mẫu, hồ sơ
│   ├── agent/                 # Director Agent, Critic, tools
│   ├── plan/                  # Pydantic schema Edit Plan, validate, diff
│   ├── effects/               # Effect Registry + plugin ffmpeg/ai
│   ├── render/                # orchestration, GPU queue, cache, mix audio
│   ├── export/                # MP4, OTIO
│   └── cli.py                 # director edit input.mp4 --style "..."
├── remotion/                  # lớp phủ: captions, titles, transitions...
├── studio/                    # Next.js UI
├── assets/                    # LUT, font, sfx, nhạc
└── tests/
```

---

## 6. Lộ trình

| Mốc | Nội dung | Xong khi |
|---|---|---|
| **M1: Nền móng** | Schema Edit Plan, CLI, Perception cơ bản (whisper, silence, scene), render ffmpeg + Remotion phụ đề, ghép lớp | `director edit in.mp4 --style "cắt im lặng, phụ đề to"` ra MP4 đúng |
| **M2: Đẹp hơn** | Khung hình linh hoạt theo lệnh (mọi tỉ lệ, nhiều khung một lúc), reframe theo mặt, punch-in theo nhấn giọng, LUT, khử ồn, nhạc + ducking, SFX, cắt từ đệm và retake | Video nói chuyện ra chất lượng đăng TikTok được |
| **M3: Bộ não** | Director Agent dùng tool, Style DNA từ câu chữ, Effect Registry | Mô tả tự do → kế hoạch dựng hợp lý |
| **M4: Tự sửa** | Bản nháp nhanh, Critic Loop, render theo cache | Điểm Critic tăng sau mỗi vòng |
| **M5: Studio** | Web UI, sửa bằng chat, nhiều phương án, xuất OTIO | Dùng hằng ngày không cần dòng lệnh |
| **M6: Đi trước** | Style DNA từ video mẫu, bộ nhớ sở thích, B-roll tự động, AI ops (tách nền, xoá vật thể, slow motion), điểm giữ chân | "Edit giống video này" cho ra kết quả nhận ra được phong cách |

---

## 7. Rủi ro và lưu ý

- **Giấy phép Remotion:** miễn phí cho cá nhân và công ty tối đa 3 người, lớn hơn cần mua license. Vì Remotion chỉ nằm ở lớp phủ, có thể thay bằng Revideo nếu cần.
- **Bản quyền nhạc và B-roll:** chỉ dùng nguồn có giấy phép rõ ràng (Pexels, Pixabay, YouTube Audio Library, thư viện tự mua). Lưu nguồn của mọi asset vào Edit Plan.
- **Giọng nói nhân bản / sửa lời bằng AI** (nếu thêm sau này): chỉ dùng với giọng của chính bạn hoặc người đã đồng ý.
- **Chi phí API:** Critic Loop tốn nhất. Có giới hạn vòng, cache, và chế độ "tiết kiệm".
- **8 GB VRAM:** một số model AI nặng phải chạy ở độ phân giải thấp hoặc theo đoạn. Chừa sẵn tuỳ chọn chuyển sang cloud GPU (Replicate, fal.ai) cho từng hiệu ứng.
