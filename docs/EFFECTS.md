# Thư viện hiệu ứng của Director

Đây là danh mục đầy đủ các hiệu ứng tool dùng được. Mỗi hiệu ứng là một plugin trong Effect Registry (xem `DESIGN.md`, mục ⑤), có `id` để Director Agent gọi trong Edit Plan.

**Cột "Chạy bằng":** `R` = Remotion (lớp phủ đồ hoạ), `F` = ffmpeg (xử lý trên video), `AI` = model AI chạy trên GPU, `A` = xử lý âm thanh.

Tất cả hiệu ứng đều **chỉ thêm vào hoặc biến đổi cách hiển thị** video gốc, không xoá hay che nội dung bạn đã làm.

---

## 1. Chuyển cảnh (transitions)

| id | Tên | Chạy bằng | Hợp với |
|---|---|---|---|
| `cut` | Cắt thẳng | F | Mặc định, nhịp nhanh |
| `jump_cut` | Jump cut (cắt nhảy cùng góc) | F | Rút gọn thoại |
| `j_cut` / `l_cut` | Âm thanh đi trước / theo sau hình | F | Chuyển cảnh mượt, tự nhiên |
| `match_cut` | Cắt khớp hình dáng/chuyển động giữa hai cảnh (agent tìm cặp cảnh giống nhau bằng embedding) | F | Chuyển cảnh "nghệ" |
| `crossfade` | Hoà tan | F | Thời gian trôi, hồi tưởng |
| `fade_black` / `fade_white` | Mờ dần sang đen / trắng | F | Kết đoạn, cliffhanger / hồi tưởng, giấc mơ |
| `dip_color` | Chớp qua một màu bất kỳ | F | Đổi tâm trạng |
| `flash_white` | Chớp trắng nhanh | R | Sốc, lộ bí mật |
| `whip_pan` | Lia nhanh có nhoè chuyển động | R | Nhịp nhanh, chuyển chủ đề |
| `zoom_blur` | Zoom xuyên nhoè | R | Năng lượng cao |
| `zoom_in_out` | Zoom vào cảnh A, zoom ra cảnh B | R | TikTok |
| `spin` | Xoay 360° chuyển cảnh | R | Hài, vui |
| `slide` | Trượt trái/phải/lên/xuống | R | Liệt kê, so sánh |
| `push` | Cảnh mới đẩy cảnh cũ ra | R | Chuyển phần |
| `wipe` | Gạt ngang/chéo/tròn/đồng hồ | R | Phong cách cổ điển |
| `iris` | Mở/đóng hình tròn | R | Hài, kiểu phim cũ |
| `shape_mask` | Chuyển qua hình trái tim/ngôi sao/chữ | R | Lãng mạn, dễ thương |
| `glitch_cut` | Chuyển cảnh nhiễu số | R | Plot twist, hồi hộp |
| `film_burn` | Cháy phim | R | Hồi tưởng, hoài niệm |
| `light_leak` | Lóa sáng | R | Ấm áp, lãng mạn |
| `ink_bleed` | Mực loang | R | Hoạt hình, cổ trang |
| `page_turn` | Lật trang | R | Kể chuyện, "chương mới" |
| `manga_panel` | Chuyển qua các ô truyện tranh | R | Hoạt hình |
| `shatter` | Vỡ kính | R | Sốc, đổ vỡ tình cảm |
| `smash_cut` | Cắt phũ từ yên tĩnh sang ồn ào (hoặc ngược lại) | F | Hài, tương phản |
| `freeze_wipe` | Dừng hình rồi gạt sang cảnh mới | R | Giới thiệu nhân vật |

## 2. Chuyển động máy quay (camera)

| id | Tên | Chạy bằng | Hợp với |
|---|---|---|---|
| `punch_in` | Zoom giật vào (đột ngột) | R | Nhấn mạnh câu thoại |
| `snap_zoom` | Zoom giật nhiều nấc liên tiếp | R | Sốc, hài |
| `slow_push` | Đẩy vào chậm | R | Căng thẳng, xúc động |
| `slow_pull` | Kéo ra chậm | R | Cô đơn, kết thúc |
| `ken_burns` | Lia + zoom chậm trên cảnh tĩnh | R | Hoạt hình giữ khung lâu |
| `pan` | Lia ngang/dọc trong khung | R | Khoe toàn cảnh |
| `dolly_zoom` | Vertigo: chủ thể giữ nguyên, nền co giãn (xấp xỉ bằng tách nền) | AI+R | Nhận ra sự thật |
| `shake` | Rung (nhẹ / vừa / động đất) | R | Sốc, giận, va chạm |
| `handheld` | Rung nhẹ liên tục như cầm tay | R | Chân thực, hồi hộp |
| `impact_bump` | Nảy khung một nhịp theo beat/tiếng động | R | Đồng bộ nhạc, cú đánh |
| `tilt` / `dutch_angle` | Nghiêng khung | R | Bất an, phản diện |
| `rotate_wobble` | Lắc lư | R | Say, chóng mặt, hài |
| `follow_character` | Khung bám nhân vật (reframe) | AI+F | Khung dọc |
| `reaction_zoom` | Zoom cận vào mặt người nghe | AI+R | Phản ứng của nhân vật |
| `split_focus` | Chuyển tiêu điểm giữa hai nhân vật | AI+R | Đối thoại căng thẳng |
| `parallax_3d` | Ảnh tĩnh thành 3D có chiều sâu (ước lượng độ sâu) | AI+R | Cảnh tĩnh, poster |

## 3. Tốc độ và thời gian

| id | Tên | Chạy bằng | Hợp với |
|---|---|---|---|
| `speed` | Nhanh/chậm cố định | F | Rút gọn, nhấn mạnh |
| `speed_ramp` | Tăng/giảm tốc độ mượt trong một clip | F | Hành động, TikTok |
| `slow_hold` | Làm chậm bằng giữ khung (mặc định cho hoạt hình) | F | Buồn, khoảnh khắc đắt |
| `slow_interp` | Làm chậm bằng nội suy khung (RIFE) | AI | Video người thật |
| `freeze_frame` | Dừng hình | F | Giới thiệu nhân vật, cliffhanger |
| `freeze_intro` | Dừng hình + tên nhân vật + chú thích | R | "Đây là Mai, 25 tuổi..." |
| `rewind` | Tua ngược có hiệu ứng VHS | R+F | "Quay lại trước đó..." |
| `reverse` | Phát ngược | F | Hài |
| `boomerang` | Tới lui lặp lại | F | Biểu cảm hài |
| `replay` | Phát lại khoảnh khắc (có thể chậm + zoom) | F | Cú tát, cú ngã |
| `stutter` | Lặp giật vài khung | F | Sốc, nhấn mạnh |
| `time_skip` | Nhảy thời gian + chữ "3 ngày sau..." | R | Chuyển mốc thời gian |
| `timelapse` | Tua nhanh nhiều | F | Thời gian trôi |

## 4. Phụ đề (caption presets)

| id | Kiểu | Hợp với |
|---|---|---|
| `classic` | Trắng viền đen, 1–2 dòng | An toàn, mọi nền tảng |
| `word_pop` | Từng từ bật lên | TikTok, Shorts |
| `karaoke` | Tô màu chạy theo từng từ đang nói | Năng động |
| `highlight_keyword` | Từ khoá đổi màu + to hơn | Nhấn ý chính |
| `box` | Chữ trong khối nền màu | Dễ đọc trên nền rối |
| `color_by_character` | Mỗi nhân vật một màu (giữ cả bộ phim) | Drama nhiều nhân vật |
| `speech_bubble` | Bong bóng thoại cạnh nhân vật đang nói | Hoạt hình, truyện tranh |
| `emotion_style` | Đổi kiểu theo cảm xúc: rung khi hét, nhỏ nghiêng khi thì thầm, run khi sợ, nhoè khi khóc | Drama |
| `typewriter` | Gõ từng chữ | Hồi hộp, tin nhắn |
| `bounce` | Nảy | Vui, hài |
| `glitch_text` | Chữ nhiễu | Plot twist |
| `handwritten` | Chữ viết tay hiện dần | Nhẹ nhàng, tâm sự |
| `neon` | Chữ phát sáng | Đêm, ngầu |
| `gradient` | Chữ chuyển màu | Trẻ trung |
| `emoji_auto` | Tự chèn emoji hợp nội dung sau từ khoá | TikTok |
| `inner_voice` | Kiểu riêng cho lời nghĩ trong đầu (nghiêng, mờ, ngoặc) | Độc thoại nội tâm |
| `sfx_text` | Chữ tượng thanh to ("RẦM!", "BỐP!") | Hoạt hình, va chạm |

Font mặc định đều **hỗ trợ đầy đủ dấu tiếng Việt**: Be Vietnam Pro, Montserrat, Oswald, Lexend, Baloo 2, Roboto. Font mới được tool kiểm tra dấu trước khi dùng.

## 5. Chữ và tiêu đề

| id | Tên | Hợp với |
|---|---|---|
| `title_slam` | Chữ đập mạnh vào màn hình + rung | Hook, tiêu đề tập |
| `title_reveal` | Chữ hiện ra sau vệt sáng / mặt nạ | Mở đầu sang trọng |
| `title_split` | Chữ tách đôi, trượt ra | Chuyển phần |
| `kinetic_type` | Chữ chuyển động theo nhịp lời nói | Câu thoại đắt |
| `lower_third` | Thanh tên nhân vật ở dưới | Giới thiệu nhân vật |
| `character_card` | Thẻ nhân vật: tên, vai, quan hệ ("Mẹ chồng – khó tính") | Drama |
| `relationship_map` | Sơ đồ quan hệ nhân vật có mũi tên | Mở đầu phần mới |
| `chapter_card` | Thẻ chương/phần ("Phần 2: Bí mật") | Video dài, nhiều phần |
| `question_hook` | Câu hỏi gợi tò mò ở đầu ("Vì sao cô ấy bỏ đi?") | Hook |
| `countdown` | Đếm ngược | Hồi hộp |
| `warning_label` | Nhãn cảnh báo / "PHẢN DIỆN" | Phản diện xuất hiện |
| `arrow_callout` | Mũi tên + chữ chỉ vào chi tiết | Chi tiết quan trọng |
| `circle_highlight` | Khoanh tròn chi tiết (vẽ tay) | Manh mối, chi tiết ẩn |
| `fake_chat` | Màn hình tin nhắn mô phỏng | Nhân vật nhắn tin |
| `continue_card` | "Còn tiếp...", "Phần 2 ở bình luận" | Cliffhanger |
| `cta` | Nút đăng ký / theo dõi / thả tim | Kết video |
| `end_screen` | Màn hình kết có chỗ cho video gợi ý | YouTube |

## 6. Hiệu ứng đặc trưng hoạt hình / manga

| id | Tên | Hợp với |
|---|---|---|
| `speed_lines` | Vệt tốc độ | Chạy, lao tới |
| `focus_lines` | Đường tập trung (集中線) hướng vào nhân vật | Sốc, quyết tâm |
| `impact_frame` | Khung va chạm đen trắng đảo màu 2–3 khung | Cú đánh, cú tát |
| `anger_vein` | Gân giận ✚ | Giận dữ |
| `sweat_drop` | Giọt mồ hôi | Bối rối, cạn lời |
| `blush` | Má hồng | Ngại ngùng, thích |
| `sparkle` | Lấp lánh | Đẹp trai/xinh, ngưỡng mộ |
| `hearts` | Tim bay | Lãng mạn |
| `gloom` | Mây đen / sọc u ám trên đầu | Buồn, thất vọng |
| `shock_lines` | Sọc dọc sau lưng + nền tối | Bàng hoàng |
| `aura` | Hào quang / lửa quanh nhân vật | Nổi giận, bùng nổ |
| `dark_aura` | Khí đen | Phản diện |
| `tears_overlay` | Hiệu ứng lệ tuôn | Khóc |
| `question_marks` / `exclamation` | ?? / !! trên đầu | Khó hiểu / bất ngờ |
| `chibi_pop` | Khung nhỏ phóng to biểu cảm hài | Hài |
| `manga_freeze` | Dừng hình thành tranh manga đen trắng có viền | Khoảnh khắc biểu tượng |
| `comic_halftone` | Chấm halftone kiểu truyện tranh | Phong cách comic |
| `panel_split` | Chia màn hình thành ô truyện tranh, mỗi ô một cảnh | Tóm tắt nhanh |
| `screen_crack` | Màn hình nứt | Đổ vỡ, sốc nặng |

Các hiệu ứng gắn lên nhân vật (gân giận, má hồng, mồ hôi...) dùng vị trí mặt nhân vật từ Perception để **đặt đúng chỗ và di chuyển theo nhân vật**.

## 7. Màu và ánh sáng

| id | Tên | Chạy bằng | Hợp với |
|---|---|---|---|
| `lut` | Áp LUT màu (.cube), có cường độ | F | Tông chung cả video |
| `auto_color` | Cân bằng sáng/màu tự động | F | Video gốc chưa đều màu |
| `match_color` | Đồng bộ màu giữa các cảnh | F | Nhiều nguồn cảnh |
| `desaturate` | Giảm màu | F | Buồn |
| `black_white` | Đen trắng | F | Hồi tưởng, cú sốc |
| `sepia` | Nâu cũ | F | Quá khứ |
| `tint` | Ám màu (đỏ giận, xanh lạnh, tím bí ẩn) | F | Theo cảm xúc |
| `color_pop` | Giữ một màu, còn lại đen trắng | AI+F | Chi tiết quan trọng |
| `vignette` | Tối viền | F | Tập trung, u buồn |
| `glow` / `bloom` | Toả sáng | R | Mơ màng, lãng mạn |
| `light_rays` | Tia sáng | R | Hy vọng, xuất hiện ấn tượng |
| `flicker` | Đèn chập chờn | R | Kinh dị, căng thẳng |
| `lightning` | Chớp sét | R | Sốc, phản diện |
| `day_to_night` | Chuyển tông ngày sang đêm | F | Thời gian trôi |
| `sharpen` / `upscale` | Làm nét / nâng độ phân giải (Real-ESRGAN anime) | F / AI | Khi đổi khung bị mờ |

## 8. Phong cách hình (stylize)

| id | Tên | Hợp với |
|---|---|---|
| `film_grain` | Hạt phim | Điện ảnh |
| `vhs` | Băng VHS: nhoè, sọc, ngày giờ góc màn hình | Hồi tưởng, hoài niệm |
| `old_film` | Phim cũ: xước, rung, viền | Ngày xưa |
| `glitch` | Nhiễu số, lệch màu RGB | Plot twist, kỹ thuật số |
| `chromatic` | Tách màu viền | Choáng, sốc |
| `blur` / `radial_blur` | Mờ / mờ toả tâm | Choáng, mất ý thức |
| `dream` | Mơ màng: mờ viền + sáng | Giấc mơ, hồi tưởng |
| `letterbox` | Viền đen điện ảnh | Điện ảnh |
| `mirror` / `kaleidoscope` | Soi gương / kính vạn hoa | Ảo giác, hài |
| `pixelate` | Vỡ điểm ảnh | Hài, kiểu game |
| `cctv` | Khung camera giám sát | "Bị theo dõi" |
| `phone_frame` | Đặt cảnh trong khung điện thoại | Xem trên mạng, livestream |
| `tv_frame` | Đặt cảnh trong TV cũ | Tin tức, hài |
| `security_red` | Viền đỏ nhấp nháy cảnh báo | Nguy hiểm |

## 9. Hạt và lớp phủ không khí (particles / overlay)

| id | Tên | Hợp với |
|---|---|---|
| `rain` | Mưa | Buồn, chia tay |
| `snow` | Tuyết | Lãng mạn, cô đơn |
| `petals` | Cánh hoa rơi | Lãng mạn, đẹp |
| `leaves` | Lá rơi | Mùa thu, buồn |
| `dust` | Bụi lơ lửng trong nắng | Yên bình |
| `fireflies` | Đom đóm | Đêm, lãng mạn |
| `confetti` | Pháo giấy | Ăn mừng, chiến thắng |
| `fire_embers` | Tàn lửa | Giận dữ, chiến đấu |
| `smoke` | Khói | Bí ẩn, phản diện |
| `bubbles` | Bong bóng | Dễ thương |
| `money_rain` | Tiền rơi | Giàu có, "trả thù ngọt ngào" |

## 10. Bố cục màn hình (layout)

| id | Tên | Hợp với |
|---|---|---|
| `fit_blur` | Giữ trọn khung, nền mờ phía sau | Đổi khung khi có sub sẵn |
| `fit_pad` | Giữ trọn khung, nền màu/thiết kế | Tối giản, có chữ ở viền |
| `split_vertical` / `split_horizontal` | Chia đôi màn hình | Hai nhân vật đối đầu |
| `pip` | Khung nhỏ trong khung lớn | Phản ứng nhân vật |
| `reaction_split` | Cảnh chính + mặt người phản ứng | "Phản ứng của mẹ chồng" |
| `before_after` | Trước / sau có thanh kéo | Thay đổi, lột xác |
| `grid` | Lưới 2×2, 3×3 nhiều cảnh | Tóm tắt nhanh, montage |
| `stacked_title` | Video giữa, tiêu đề trên, phụ đề dưới | Khung dọc từ video ngang |
| `progress_bar` | Thanh tiến trình | Giữ chân người xem |
| `episode_badge` | Huy hiệu "Tập 12", "Phần 2/3" ở góc | Phim nhiều tập |
| `watermark` | Logo/tên kênh (bạn đưa vào hoặc tạo từ tên kênh) | Thương hiệu |

## 11. Âm thanh

### 11.1 Tiếng động (SFX), theo bộ

| Bộ | Gồm |
|---|---|
| `drama` | dun dun dun, nhấn trầm (boom), nhịp tim, tiếng thở dốc, đồng hồ tích tắc, gió rít, record scratch, tiếng hét dội |
| `transition` | whoosh (nhanh/chậm/nặng), swoosh, riser (dâng lên), downer (hạ xuống), reverse cymbal |
| `impact` | bốp, rầm, tát, đấm, vỡ kính, đóng cửa sầm, sấm |
| `comedy` | boing, quạ kêu, dế kêu (im lặng ngượng), kèn trombone buồn (wah wah), cười đóng hộp, pop, ding |
| `ui` | click, pop, ting, ding thông báo, tiếng gõ phím, tiếng chụp ảnh |
| `emotion` | ồ (ngạc nhiên đám đông), awww, vỗ tay, nhịp tim chậm, tiếng chuông gió |
| `ambient` | mưa, gió, quán cà phê, đường phố, đêm côn trùng, sóng biển |
| `anime` | sparkle, swish, tiếng "shing" rút kiếm, tiếng aura, tiếng dịch chuyển tức thời |

SFX tự đặt khớp với hiệu ứng hình (zoom giật đi với "bốp", chuyển cảnh whip đi với "whoosh"...) và **khớp chính xác vào khung hình xảy ra hành động**.

### 11.2 Nhạc nền

| id | Làm gì |
|---|---|
| `bgm_by_emotion` | Tự đổi nhạc theo cảm xúc từng đoạn: căng thẳng, buồn, vui, hài, lãng mạn, kinh dị, hùng tráng |
| `keep_original_bgm` | Giữ nhạc gốc của video (tách bằng Demucs), chỉ chỉnh to nhỏ |
| `beat_sync` | Cắt / zoom / hiệu ứng trúng beat nhạc |
| `ducking` | Tự giảm nhạc khi có thoại |
| `music_drop` | Tắt nhạc đột ngột trước câu thoại sốc (khoảng lặng kịch tính) |
| `music_swell` | Nhạc dâng lên ở cao trào |
| `crossfade_music` | Chuyển nhạc mượt giữa các đoạn |
| `stinger` | Một đoạn nhạc ngắn nhấn mạnh (2–3 giây) |

### 11.3 Hiệu ứng giọng và âm thanh

| id | Tên | Hợp với |
|---|---|---|
| `denoise` | Khử ồn | Mọi video |
| `voice_enhance` | Làm giọng rõ, ấm (EQ + nén) | Mọi video |
| `loudnorm` | Chuẩn âm lượng theo nền tảng (-14 LUFS) | Mọi video |
| `echo` / `reverb` | Vọng / vang | Lời nghĩ trong đầu, hồi tưởng |
| `muffled` | Nghe như sau tường / dưới nước | Choáng, ngất, nghe lén |
| `radio` / `phone` | Giọng qua điện thoại / radio | Gọi điện |
| `pitch_up` / `pitch_down` | Giọng cao (chipmunk) / trầm (ác quỷ) | Hài / phản diện |
| `slow_audio` | Âm thanh chậm theo hình | Slow motion |
| `tape_stop` | Âm thanh chậm dần tắt | Cú sốc, "đứng hình" |
| `bass_boost` | Tăng trầm | Va chạm, ngầu |
| `stereo_pan` | Âm thanh di chuyển trái/phải theo nhân vật | Sống động |
| `silence_beat` | Một nhịp im lặng tuyệt đối | Trước twist |

---

## 12. Combo hiệu ứng (preset)

Agent thường dùng **combo** thay vì từng hiệu ứng lẻ, để kết quả đồng bộ và có chủ đích:

| Combo | Gồm | Dùng khi |
|---|---|---|
| `combo.shock` | `music_drop` → `snap_zoom` + `shake` + `flash_white` + `focus_lines` + SFX "dun dun" + `sfx_text` | Lộ bí mật, twist |
| `combo.slap` | `impact_frame` + `shake` mạnh + `replay` chậm + SFX tát + `exclamation` | Cú tát, cú đánh |
| `combo.sad` | `slow_push` + `desaturate` + `vignette` + `rain` hoặc `petals` + nhạc piano + `slow_hold` | Chia tay, mất mát |
| `combo.anger` | `tint` đỏ + `aura` + `shake` liên tục + `anger_vein` + nhịp tim nhanh | Nổi giận |
| `combo.villain` | `dutch_angle` + `dark_aura` + `tint` tối + `warning_label` + nhạc trầm | Phản diện xuất hiện |
| `combo.romance` | `glow` + `hearts` + `sparkle` + `blush` + `light_leak` + nhạc lãng mạn | Khoảnh khắc tình cảm |
| `combo.comedy` | `boomerang` hoặc `stutter` + `chibi_pop` + `sweat_drop` + SFX quạ/boing | Cạn lời, hài |
| `combo.revenge` | `speed_ramp` + `light_rays` + `money_rain` hoặc `confetti` + nhạc hùng tráng | Trả thù ngọt ngào, lật kèo |
| `combo.flashback` | `rewind` + `sepia` hoặc `dream` + `reverb` trên thoại + `time_skip` | Hồi tưởng |
| `combo.hook` | Cảnh căng nhất + `title_slam` hoặc `question_hook` + `stinger` → `rewind` về đầu | 3 giây đầu |
| `combo.cliffhanger` | `freeze_frame` + `music_swell` → `silence_beat` + `fade_black` + `continue_card` | Kết phần |
| `combo.intro_character` | `freeze_intro` + `character_card` + SFX "swish" | Nhân vật xuất hiện lần đầu |

---

## 13. Quy tắc dùng hiệu ứng (để hay chứ không rối)

Có nhiều hiệu ứng không có nghĩa là dùng hết. Director có các luật sau, và Critic kiểm tra lại từng luật:

1. **Ngân sách theo phong cách:** Style DNA quy định mật độ (ví dụ "drama năng động": tối đa 1 combo mạnh mỗi 15 giây, 1 hiệu ứng nhỏ mỗi 3–5 giây). Lệnh "nhiều hiệu ứng hơn" / "tối giản thôi" sẽ thay đổi ngân sách.
2. **Có lý do:** mỗi hiệu ứng phải gắn với một sự kiện trong video (câu thoại, cảm xúc, beat nhạc, chuyển cảnh). Agent ghi lý do vào Edit Plan.
3. **Không lặp liền nhau:** cùng một hiệu ứng không xuất hiện hai lần liên tiếp. Có thời gian nghỉ (cooldown) cho mỗi hiệu ứng.
4. **Leo thang theo câu chuyện:** đầu video nhẹ, cao trào mạnh nhất. Combo mạnh nhất để dành cho twist.
5. **Khoảng thở:** sau một combo mạnh phải có vài giây yên tĩnh.
6. **Không che nội dung:** hiệu ứng và chữ không đè lên mặt nhân vật, phụ đề có sẵn hay vùng nút bấm của nền tảng.
7. **Đồng bộ hình và tiếng:** hiệu ứng hình có tiếng động đi kèm thì phải khớp đúng khung hình.
8. **Nhất quán cả bộ phim:** màu nhân vật, font, bộ SFX, kiểu chuyển cảnh giữ nguyên giữa các tập.

---

## 14. Nguồn tài nguyên (âm thanh, nhạc, font, overlay)

- **Font:** Google Fonts (giấy phép OFL), chỉ chọn font có dấu tiếng Việt.
- **SFX và nhạc:** Pixabay (Content License), Freesound (lọc CC0), YouTube Audio Library, hoặc thư viện bạn đã mua. Mỗi file ghi rõ nguồn và giấy phép trong `assets/manifest.json`.
- **Overlay (mưa, tuyết, lóa sáng, cháy phim...):** phần lớn **tự vẽ bằng code** trong Remotion (hạt, gradient, shader), nên không lo giấy phép và đổi màu/mật độ được. Overlay dạng video chỉ dùng nguồn có giấy phép rõ.
- **Hiệu ứng manga** (đường tập trung, vệt tốc độ, gân giận, mồ hôi...): vẽ bằng SVG/code, đổi được màu, độ dày, hướng.
- **Thêm tài nguyên của riêng bạn:** thả file vào `assets/` (SFX, nhạc, LUT, logo, font), tool tự quét, phân loại và đưa vào Registry.
