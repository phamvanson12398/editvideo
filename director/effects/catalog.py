"""Effect Registry: every effect Director can use (mirrors docs/EFFECTS.md).

category decides who renders it:
  edit        compiler only (cut types)
  overlap     Remotion transition that shows both clips (needs handles)
  tx          Remotion transition done with transforms/overlays around the cut
  camera      Remotion transform of the video layer
  time        compiler rewrites clips (speed, freeze, reverse...)
  color       Remotion CSS/SVG filter on the video layer (prep-* = ffmpeg at clip prep)
  stylize     Remotion filters/overlays on the video layer
  manga       Remotion SVG overlays (optionally anchored to a face)
  particles   Remotion particle overlays
  text        Remotion text/graphics overlays
  layout      Remotion layout of the video layer / persistent UI
  audio       ffmpeg audio filters (clip-level) or timeline volume automation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EffectDef:
    id: str
    category: str
    name: str  # Vietnamese display name
    desc: str
    dur: float = 0.6  # default duration (output seconds)
    strength: str = "small"  # small | strong
    params: dict[str, Any] = field(default_factory=dict)  # defaults
    sfx: str | None = None  # SFX automatically paired with it
    anchor: str | None = None  # "face" when it should follow a character
    moods: tuple[str, ...] = ()  # emotions it fits


EFFECTS: dict[str, EffectDef] = {}


def E(id: str, category: str, name: str, desc: str, **kw: Any) -> None:
    EFFECTS[id] = EffectDef(id=id, category=category, name=name, desc=desc, **kw)


# ---------------------------------------------------------------- 1. transitions
E("cut", "edit", "Cắt thẳng", "Cắt thẳng, mặc định", dur=0.0)
E("jump_cut", "edit", "Jump cut", "Cắt nhảy cùng góc để rút gọn thoại", dur=0.0)
E("j_cut", "edit", "J-cut", "Âm thanh cảnh sau vào trước hình", dur=0.4, params={"audio_lead": 0.4})
E("l_cut", "edit", "L-cut", "Âm thanh cảnh trước kéo sang hình sau", dur=0.4, params={"audio_tail": 0.4})
E("match_cut", "edit", "Match cut", "Cắt khớp hình giữa hai cảnh giống nhau", dur=0.0)
E("smash_cut", "edit", "Smash cut", "Cắt phũ từ yên tĩnh sang ồn ào", dur=0.0, sfx="impact_boom", moods=("comedy", "shock"))
E("crossfade", "overlap", "Hoà tan", "Hoà tan hai cảnh", dur=0.6, moods=("sad", "romance"))
E("fade_black", "tx", "Mờ sang đen", "Mờ dần sang đen rồi hiện cảnh mới", dur=0.8, params={"color": "#000000"}, moods=("sad",))
E("fade_white", "tx", "Mờ sang trắng", "Mờ dần sang trắng (hồi tưởng, giấc mơ)", dur=0.8, params={"color": "#FFFFFF"})
E("dip_color", "tx", "Chớp qua màu", "Chớp qua một màu bất kỳ", dur=0.5, params={"color": "#FF2D55"})
E("flash_white", "tx", "Chớp trắng", "Chớp trắng nhanh", dur=0.35, strength="strong", sfx="hit_flash", moods=("shock",))
E("whip_pan", "tx", "Whip pan", "Lia nhanh có nhoè chuyển động", dur=0.35, params={"direction": "left"}, sfx="whoosh_fast")
E("zoom_blur", "tx", "Zoom xuyên", "Zoom xuyên nhoè", dur=0.4, sfx="whoosh_heavy")
E("zoom_in_out", "tx", "Zoom vào-ra", "Zoom vào cảnh A, zoom ra cảnh B", dur=0.5, sfx="whoosh_fast")
E("spin", "tx", "Xoay chuyển cảnh", "Xoay 360°", dur=0.5, sfx="swoosh", moods=("comedy",))
E("slide", "overlap", "Trượt", "Cảnh mới trượt vào", dur=0.45, params={"direction": "left"}, sfx="swoosh")
E("push", "overlap", "Đẩy", "Cảnh mới đẩy cảnh cũ ra", dur=0.45, params={"direction": "left"}, sfx="swoosh")
E("wipe", "overlap", "Gạt", "Gạt ngang/chéo/tròn", dur=0.5, params={"shape": "linear", "direction": "left"})
E("iris", "overlap", "Mở hình tròn", "Mở/đóng hình tròn kiểu phim cũ", dur=0.6, moods=("comedy",))
E("shape_mask", "overlap", "Chuyển qua hình", "Chuyển qua hình trái tim/ngôi sao", dur=0.6, params={"shape": "heart"}, moods=("romance",))
E("glitch_cut", "tx", "Glitch", "Chuyển cảnh nhiễu số", dur=0.4, strength="strong", sfx="glitch", moods=("shock", "villain"))
E("film_burn", "tx", "Cháy phim", "Cháy phim, hoài niệm", dur=0.8)
E("light_leak", "tx", "Lóa sáng", "Lóa sáng ấm", dur=0.8, moods=("romance", "happy"))
E("ink_bleed", "tx", "Mực loang", "Mực loang (hoạt hình, cổ trang)", dur=0.8)
E("page_turn", "overlap", "Lật trang", "Lật trang, chương mới", dur=0.7, sfx="page_flip")
E("manga_panel", "overlap", "Ô truyện tranh", "Chuyển qua các ô truyện tranh", dur=0.7)
E("shatter", "overlap", "Vỡ kính", "Cảnh cũ vỡ như kính", dur=0.7, strength="strong", sfx="glass_break", moods=("shock", "sad"))
E("freeze_wipe", "overlap", "Dừng hình rồi gạt", "Dừng hình rồi gạt sang cảnh mới", dur=0.6)

# ---------------------------------------------------------------- 2. camera
E("punch_in", "camera", "Zoom giật vào", "Zoom đột ngột vào chủ thể", dur=0.8, params={"scale": 1.25}, anchor="face")
E("snap_zoom", "camera", "Zoom giật nhiều nấc", "Zoom giật nhiều nấc liên tiếp", dur=0.9, strength="strong", params={"steps": 3, "scale": 1.5}, anchor="face", moods=("shock", "comedy"))
E("slow_push", "camera", "Đẩy vào chậm", "Đẩy vào chậm", dur=3.0, params={"scale": 1.15}, anchor="face", moods=("sad", "fear", "romance"))
E("slow_pull", "camera", "Kéo ra chậm", "Kéo ra chậm", dur=3.0, params={"scale": 1.15}, moods=("sad",))
E("ken_burns", "camera", "Ken Burns", "Lia + zoom chậm trên cảnh tĩnh", dur=4.0, params={"scale": 1.12, "direction": "auto"})
E("pan", "camera", "Lia khung", "Lia ngang/dọc trong khung", dur=2.0, params={"direction": "right", "amount": 0.15})
E("dolly_zoom", "camera", "Vertigo", "Chủ thể giữ nguyên, nền co giãn (xấp xỉ)", dur=1.5, strength="strong", anchor="face", moods=("shock",))
E("shake", "camera", "Rung", "Rung khung", dur=0.6, params={"intensity": 0.5}, moods=("shock", "anger"))
E("handheld", "camera", "Cầm tay", "Rung nhẹ liên tục như cầm tay", dur=4.0, params={"intensity": 0.15})
E("impact_bump", "camera", "Nảy khung", "Nảy khung một nhịp", dur=0.25, params={"scale": 1.06})
E("dutch_angle", "camera", "Nghiêng khung", "Nghiêng khung (bất an, phản diện)", dur=2.0, params={"angle": 8}, moods=("villain", "fear"))
E("tilt", "camera", "Nghiêng", "Nghiêng khung nhẹ", dur=1.5, params={"angle": 4})
E("rotate_wobble", "camera", "Lắc lư", "Lắc lư (say, chóng mặt, hài)", dur=1.5, params={"angle": 5}, moods=("comedy",))
E("reaction_zoom", "camera", "Zoom phản ứng", "Zoom cận mặt người nghe", dur=1.2, params={"scale": 1.4}, anchor="face")
E("split_focus", "camera", "Chuyển tiêu điểm", "Chuyển tiêu điểm giữa hai nhân vật", dur=2.0, anchor="face")
E("zoom_hold", "camera", "Zoom giữ", "Zoom tĩnh cả clip (đổi góc khi jump cut)", dur=0.0, params={"scale": 1.08})
E("parallax_3d", "camera", "Ảnh 3D", "Cảnh tĩnh có chiều sâu (xấp xỉ)", dur=3.0, params={"scale": 1.1})

# ---------------------------------------------------------------- 3. time
E("speed", "time", "Đổi tốc độ", "Nhanh/chậm cố định", dur=0.0, params={"factor": 1.5})
E("speed_ramp", "time", "Speed ramp", "Tăng/giảm tốc mượt", dur=0.0, params={"low": 0.5, "high": 2.0})
E("slow_hold", "time", "Chậm giữ khung", "Làm chậm bằng giữ khung (hoạt hình)", dur=0.0, params={"factor": 0.5}, moods=("sad",))
E("slow_interp", "time", "Chậm nội suy", "Làm chậm bằng nội suy khung (người thật)", dur=0.0, params={"factor": 0.5})
E("freeze_frame", "time", "Dừng hình", "Dừng hình", dur=1.0, moods=("shock",))
E("freeze_intro", "time", "Dừng hình giới thiệu", "Dừng hình + tên nhân vật", dur=1.8, sfx="swish", params={"text": "", "subtitle": ""})
E("rewind", "time", "Tua ngược", "Tua ngược kiểu VHS", dur=1.2, sfx="rewind_tape")
E("reverse", "time", "Phát ngược", "Phát ngược", dur=0.0, moods=("comedy",))
E("boomerang", "time", "Boomerang", "Tới lui lặp lại", dur=0.0, moods=("comedy",))
E("replay", "time", "Phát lại", "Phát lại khoảnh khắc (chậm + zoom)", dur=0.0, strength="strong", params={"factor": 0.5, "times": 1})
E("stutter", "time", "Lặp giật", "Lặp giật vài khung", dur=0.0, params={"repeats": 3, "length": 0.15}, moods=("shock", "comedy"))
E("time_skip", "text", "Nhảy thời gian", "Chữ '3 ngày sau...'", dur=1.6, params={"text": "Một lúc sau..."})
E("timelapse", "time", "Tua nhanh", "Tua nhanh nhiều", dur=0.0, params={"factor": 6.0})

# ---------------------------------------------------------------- 5. text & titles
E("title_slam", "text", "Chữ đập", "Chữ đập mạnh + rung", dur=1.8, strength="strong", params={"text": ""}, sfx="impact_boom")
E("title_reveal", "text", "Chữ hiện sau vệt sáng", "Chữ hiện sang trọng", dur=2.0, params={"text": ""})
E("title_split", "text", "Chữ tách đôi", "Chữ tách đôi, trượt ra", dur=1.6, params={"text": ""}, sfx="swoosh")
E("kinetic_type", "text", "Chữ chuyển động", "Chữ chuyển động theo nhịp nói", dur=2.5, params={"text": ""})
E("lower_third", "text", "Thanh tên", "Thanh tên nhân vật phía dưới", dur=3.0, params={"text": "", "subtitle": ""})
E("character_card", "text", "Thẻ nhân vật", "Tên, vai, quan hệ", dur=2.5, params={"text": "", "subtitle": ""}, sfx="swish")
E("relationship_map", "text", "Sơ đồ quan hệ", "Sơ đồ quan hệ nhân vật", dur=3.5, params={"nodes": [], "edges": []})
E("chapter_card", "text", "Thẻ chương", "Thẻ chương/phần", dur=2.0, params={"text": ""}, sfx="whoosh_slow")
E("question_hook", "text", "Câu hỏi hook", "Câu hỏi gợi tò mò ở đầu", dur=2.6, params={"text": ""}, sfx="riser")
E("countdown", "text", "Đếm ngược", "Đếm ngược", dur=3.0, params={"from": 3}, sfx="tick")
E("warning_label", "text", "Nhãn cảnh báo", "Nhãn 'PHẢN DIỆN' / cảnh báo", dur=2.0, params={"text": "PHẢN DIỆN"}, sfx="alarm", moods=("villain",))
E("arrow_callout", "text", "Mũi tên chỉ", "Mũi tên + chữ chỉ chi tiết", dur=2.0, params={"text": "", "x": 0.6, "y": 0.4})
E("circle_highlight", "text", "Khoanh tròn", "Khoanh tròn chi tiết (vẽ tay)", dur=2.0, params={"x": 0.5, "y": 0.5, "r": 0.12}, anchor="face")
E("fake_chat", "text", "Tin nhắn", "Màn hình tin nhắn mô phỏng", dur=3.5, params={"messages": []}, sfx="notification")
E("continue_card", "text", "Còn tiếp", "'Còn tiếp...' cuối video", dur=2.2, params={"text": "Còn tiếp..."}, sfx="stinger_suspense")
E("cta", "text", "Kêu gọi theo dõi", "Nút đăng ký/theo dõi/thả tim", dur=2.5, params={"text": "Theo dõi để xem tiếp!"}, sfx="pop")
E("end_screen", "text", "Màn hình kết", "Màn hình kết có chỗ cho video gợi ý", dur=5.0, params={"text": "Cảm ơn đã xem!"})
E("sfx_text", "text", "Chữ tượng thanh", "Chữ to 'RẦM!', 'BỐP!'", dur=0.9, params={"text": "RẦM!"}, anchor="face", moods=("shock", "anger", "comedy"))
E("emoji_pop", "text", "Emoji", "Emoji bật lên", dur=1.2, params={"emoji": "😱"}, anchor="face")

# ---------------------------------------------------------------- 6. manga / animation
E("speed_lines", "manga", "Vệt tốc độ", "Vệt tốc độ", dur=1.0, moods=("shock", "anger"))
E("focus_lines", "manga", "Đường tập trung", "Đường tập trung (集中線)", dur=1.2, anchor="face", moods=("shock", "anger"))
E("impact_frame", "manga", "Khung va chạm", "Khung va chạm đảo màu 2–3 khung", dur=0.25, strength="strong", sfx="impact_punch", moods=("shock", "anger"))
E("anger_vein", "manga", "Gân giận", "Gân giận ✚", dur=1.5, anchor="face", moods=("anger",))
E("sweat_drop", "manga", "Giọt mồ hôi", "Giọt mồ hôi (bối rối)", dur=1.5, anchor="face", moods=("comedy", "fear"))
E("blush", "manga", "Má hồng", "Má hồng (ngại ngùng)", dur=1.8, anchor="face", moods=("romance",))
E("sparkle", "manga", "Lấp lánh", "Lấp lánh", dur=1.5, anchor="face", sfx="sparkle", moods=("romance", "happy"))
E("hearts", "manga", "Tim bay", "Tim bay", dur=2.0, anchor="face", moods=("romance",))
E("gloom", "manga", "U ám", "Mây đen / sọc u ám", dur=2.0, anchor="face", moods=("sad",))
E("shock_lines", "manga", "Sọc bàng hoàng", "Sọc dọc + nền tối", dur=1.2, anchor="face", moods=("shock",))
E("aura", "manga", "Hào quang", "Hào quang/lửa quanh nhân vật", dur=2.0, anchor="face", params={"color": "#FF5A1F"}, sfx="aura", moods=("anger",))
E("dark_aura", "manga", "Khí đen", "Khí đen phản diện", dur=2.0, anchor="face", sfx="aura", moods=("villain",))
E("tears_overlay", "manga", "Nước mắt", "Lệ tuôn", dur=2.0, anchor="face", moods=("sad",))
E("question_marks", "manga", "Dấu hỏi", "?? trên đầu", dur=1.4, anchor="face", sfx="boing", moods=("comedy",))
E("exclamation", "manga", "Dấu chấm than", "!! trên đầu", dur=1.0, anchor="face", sfx="ding", moods=("shock",))
E("chibi_pop", "manga", "Phóng to biểu cảm", "Khung nhỏ phóng to biểu cảm hài", dur=1.5, anchor="face", sfx="pop", moods=("comedy",))
E("manga_freeze", "manga", "Dừng hình manga", "Dừng hình thành tranh manga đen trắng", dur=1.5, strength="strong", moods=("shock",))
E("comic_halftone", "manga", "Halftone", "Chấm halftone kiểu truyện tranh", dur=2.0)
E("panel_split", "layout", "Chia ô truyện", "Chia màn hình thành ô truyện tranh", dur=2.0)
E("screen_crack", "manga", "Màn hình nứt", "Màn hình nứt", dur=1.2, strength="strong", sfx="glass_break", moods=("shock", "sad"))

# ---------------------------------------------------------------- 7. color & light
E("lut", "color", "LUT màu", "Áp LUT .cube (toàn video)", dur=0.0, params={"name": "warm", "intensity": 0.7})
E("auto_color", "color", "Cân màu tự động", "Cân bằng sáng/màu tự động", dur=0.0)
E("match_color", "color", "Đồng bộ màu", "Đồng bộ màu giữa các cảnh", dur=0.0)
E("desaturate", "color", "Giảm màu", "Giảm màu", dur=3.0, params={"amount": 0.6}, moods=("sad",))
E("black_white", "color", "Đen trắng", "Đen trắng", dur=2.0, moods=("shock", "sad"))
E("sepia", "color", "Nâu cũ", "Nâu cũ (quá khứ)", dur=3.0)
E("tint", "color", "Ám màu", "Ám màu theo cảm xúc", dur=2.0, params={"color": "#FF0000", "amount": 0.25})
E("color_pop", "color", "Giữ một màu", "Giữ một màu, còn lại đen trắng", dur=2.0, params={"color": "#FF0000"})
E("vignette", "stylize", "Tối viền", "Tối viền", dur=3.0, params={"amount": 0.5})
E("glow", "stylize", "Toả sáng", "Toả sáng mơ màng", dur=2.5, moods=("romance",))
E("light_rays", "stylize", "Tia sáng", "Tia sáng", dur=2.5, moods=("happy",))
E("flicker", "stylize", "Đèn chập chờn", "Đèn chập chờn", dur=1.5, moods=("fear",))
E("lightning", "stylize", "Chớp sét", "Chớp sét", dur=0.8, strength="strong", sfx="thunder", moods=("shock", "villain"))
E("day_to_night", "color", "Ngày sang đêm", "Chuyển tông ngày sang đêm", dur=3.0)
E("sharpen", "color", "Làm nét", "Làm nét (khi phóng to)", dur=0.0)
E("upscale", "color", "Nâng độ phân giải", "Real-ESRGAN anime (GPU)", dur=0.0)

# ---------------------------------------------------------------- 8. stylize
E("film_grain", "stylize", "Hạt phim", "Hạt phim", dur=3.0)
E("vhs", "stylize", "VHS", "Băng VHS", dur=2.0)
E("old_film", "stylize", "Phim cũ", "Phim cũ: xước, rung", dur=3.0)
E("glitch", "stylize", "Glitch", "Nhiễu số, lệch màu RGB", dur=0.6, strength="strong", sfx="glitch", moods=("shock", "villain"))
E("chromatic", "stylize", "Tách màu viền", "Tách màu viền", dur=0.8, moods=("shock",))
E("blur", "stylize", "Mờ", "Làm mờ", dur=1.0)
E("radial_blur", "stylize", "Mờ toả tâm", "Mờ toả tâm (choáng)", dur=0.8)
E("dream", "stylize", "Mơ màng", "Mờ viền + sáng (giấc mơ, hồi tưởng)", dur=3.0)
E("letterbox", "stylize", "Viền điện ảnh", "Viền đen điện ảnh", dur=3.0, params={"ratio": 2.39})
E("mirror", "stylize", "Soi gương", "Soi gương", dur=1.5)
E("kaleidoscope", "stylize", "Kính vạn hoa", "Kính vạn hoa", dur=1.5)
E("pixelate", "stylize", "Vỡ điểm ảnh", "Vỡ điểm ảnh", dur=1.0, moods=("comedy",))
E("cctv", "stylize", "Camera giám sát", "Khung camera giám sát", dur=3.0)
E("phone_frame", "layout", "Khung điện thoại", "Đặt cảnh trong khung điện thoại", dur=3.0)
E("tv_frame", "layout", "Khung TV cũ", "Đặt cảnh trong TV cũ", dur=3.0)
E("security_red", "stylize", "Viền đỏ cảnh báo", "Viền đỏ nhấp nháy", dur=2.0, sfx="alarm", moods=("fear", "villain"))
E("invert", "stylize", "Đảo màu", "Đảo màu", dur=0.2)

# ---------------------------------------------------------------- 9. particles
for pid, pname, moods in [
    ("rain", "Mưa", ("sad",)), ("snow", "Tuyết", ("romance", "sad")), ("petals", "Cánh hoa", ("romance",)),
    ("leaves", "Lá rơi", ("sad",)), ("dust", "Bụi nắng", ()), ("fireflies", "Đom đóm", ("romance",)),
    ("confetti", "Pháo giấy", ("happy",)), ("fire_embers", "Tàn lửa", ("anger",)), ("smoke", "Khói", ("villain", "fear")),
    ("bubbles", "Bong bóng", ("happy", "comedy")), ("money_rain", "Tiền rơi", ("happy",)),
]:
    E(pid, "particles", pname, f"Hiệu ứng hạt: {pname.lower()}", dur=3.0, params={"density": 1.0}, moods=moods)

# ---------------------------------------------------------------- 10. layout
E("fit_blur", "layout", "Giữ khung, nền mờ", "Giữ trọn khung, nền mờ phía sau", dur=0.0)
E("fit_pad", "layout", "Giữ khung, nền màu", "Giữ trọn khung, nền màu", dur=0.0, params={"color": "#111111"})
E("split_vertical", "layout", "Chia đôi dọc", "Chia đôi màn hình (trên/dưới)", dur=3.0)
E("split_horizontal", "layout", "Chia đôi ngang", "Chia đôi màn hình (trái/phải)", dur=3.0)
E("pip", "layout", "Khung trong khung", "Khung nhỏ trong khung lớn", dur=3.0, anchor="face")
E("reaction_split", "layout", "Khung phản ứng", "Cảnh chính + mặt người phản ứng", dur=3.0, anchor="face")
E("before_after", "layout", "Trước/sau", "Trước / sau có thanh kéo", dur=3.0)
E("grid", "layout", "Lưới cảnh", "Lưới 2×2 nhiều cảnh", dur=2.5)
E("stacked_title", "layout", "Tiêu đề trên-dưới", "Video giữa, tiêu đề trên", dur=0.0)
E("progress_bar", "layout", "Thanh tiến trình", "Thanh tiến trình", dur=0.0, params={"color": "#FFD400"})
E("episode_badge", "layout", "Huy hiệu tập", "Huy hiệu 'Tập 12'", dur=0.0, params={"text": ""})
E("watermark", "layout", "Logo kênh", "Logo/tên kênh", dur=0.0, params={"text": ""})

# ---------------------------------------------------------------- 11. audio fx
E("echo", "audio", "Vọng", "Tiếng vọng", params={"delay": 0.25, "decay": 0.4})
E("reverb", "audio", "Vang", "Tiếng vang (lời nghĩ, hồi tưởng)")
E("muffled", "audio", "Nghe nghẹt", "Như sau tường/dưới nước")
E("radio", "audio", "Giọng radio", "Giọng qua radio")
E("phone", "audio", "Giọng điện thoại", "Giọng qua điện thoại")
E("pitch_up", "audio", "Giọng cao", "Giọng chipmunk", moods=("comedy",))
E("pitch_down", "audio", "Giọng trầm", "Giọng ác quỷ", moods=("villain",))
E("slow_audio", "audio", "Âm thanh chậm", "Âm thanh chậm theo hình")
E("tape_stop", "audio", "Tape stop", "Âm thanh chậm dần tắt", sfx="tape_stop", moods=("shock",))
E("bass_boost", "audio", "Tăng trầm", "Tăng trầm")
E("stereo_pan", "audio", "Âm thanh di chuyển", "Âm thanh chạy trái/phải", params={"from": -0.8, "to": 0.8})
E("silence_beat", "audio", "Nhịp im lặng", "Một nhịp im lặng tuyệt đối", dur=0.5, moods=("shock",))
E("music_drop", "audio", "Tắt nhạc đột ngột", "Tắt nhạc trước câu thoại sốc", dur=1.2, moods=("shock",))
E("music_swell", "audio", "Nhạc dâng", "Nhạc dâng lên ở cao trào", dur=3.0)
E("stinger", "audio", "Stinger", "Đoạn nhạc ngắn nhấn mạnh", dur=2.0, sfx="stinger_drama")

CAPTION_PRESETS = {
    "classic": "Trắng viền đen, 1–2 dòng",
    "word_pop": "Từng từ bật lên",
    "karaoke": "Tô màu chạy theo từ đang nói",
    "highlight_keyword": "Từ khoá đổi màu + to hơn",
    "box": "Chữ trong khối nền màu",
    "color_by_character": "Mỗi nhân vật một màu",
    "speech_bubble": "Bong bóng thoại cạnh nhân vật",
    "emotion_style": "Đổi kiểu theo cảm xúc",
    "typewriter": "Gõ từng chữ",
    "bounce": "Nảy",
    "glitch_text": "Chữ nhiễu",
    "handwritten": "Chữ viết tay",
    "neon": "Chữ phát sáng",
    "gradient": "Chữ chuyển màu",
    "inner_voice": "Lời nghĩ trong đầu",
}

# ---------------------------------------------------------------- 12. combos
# Each step: (effect id or "sfx:<id>", offset seconds from the anchor, duration or None, params)
COMBOS: dict[str, dict[str, Any]] = {
    "combo.shock": {
        "name": "Sốc / lộ bí mật", "moods": ("shock",),
        "steps": [
            ("music_drop", -0.9, 1.2, {}), ("snap_zoom", 0.0, 0.9, {}), ("shake", 0.0, 0.6, {"intensity": 0.6}),
            ("flash_white", 0.0, 0.3, {}), ("focus_lines", 0.0, 1.2, {}), ("sfx:dun_dun_dun", 0.0, None, {}),
        ],
    },
    "combo.slap": {
        "name": "Cú tát / cú đánh", "moods": ("anger",),
        "steps": [
            ("impact_frame", 0.0, 0.25, {}), ("shake", 0.0, 0.7, {"intensity": 0.9}), ("replay", 0.0, None, {"factor": 0.5}),
            ("exclamation", 0.1, 1.0, {}), ("sfx:slap", 0.0, None, {}),
        ],
    },
    "combo.sad": {
        "name": "Buồn / mất mát", "moods": ("sad",),
        "steps": [
            ("slow_push", 0.0, 3.0, {}), ("desaturate", 0.0, 3.0, {"amount": 0.5}), ("vignette", 0.0, 3.0, {}),
            ("rain", 0.0, 3.0, {"density": 0.7}), ("slow_hold", 0.0, None, {"factor": 0.7}),
        ],
    },
    "combo.anger": {
        "name": "Nổi giận", "moods": ("anger",),
        "steps": [
            ("tint", 0.0, 1.8, {"color": "#FF0000", "amount": 0.25}), ("aura", 0.0, 1.8, {}), ("shake", 0.0, 1.2, {"intensity": 0.35}),
            ("anger_vein", 0.1, 1.5, {}), ("sfx:heartbeat_fast", 0.0, None, {}),
        ],
    },
    "combo.villain": {
        "name": "Phản diện xuất hiện", "moods": ("villain",),
        "steps": [
            ("dutch_angle", 0.0, 2.0, {}), ("dark_aura", 0.0, 2.0, {}), ("tint", 0.0, 2.0, {"color": "#3A0066", "amount": 0.3}),
            ("warning_label", 0.2, 1.8, {}), ("sfx:villain_hit", 0.0, None, {}),
        ],
    },
    "combo.romance": {
        "name": "Lãng mạn", "moods": ("romance",),
        "steps": [
            ("glow", 0.0, 2.5, {}), ("hearts", 0.0, 2.0, {}), ("sparkle", 0.2, 1.5, {}), ("blush", 0.0, 1.8, {}),
            ("light_leak", 0.0, 0.8, {}),
        ],
    },
    "combo.comedy": {
        "name": "Hài / cạn lời", "moods": ("comedy",),
        "steps": [
            ("stutter", 0.0, None, {}), ("chibi_pop", 0.0, 1.5, {}), ("sweat_drop", 0.2, 1.5, {}), ("sfx:crow", 0.3, None, {}),
        ],
    },
    "combo.revenge": {
        "name": "Trả thù / lật kèo", "moods": ("happy",),
        "steps": [
            ("speed_ramp", 0.0, None, {}), ("light_rays", 0.0, 2.5, {}), ("money_rain", 0.0, 2.5, {}), ("sfx:stinger_epic", 0.0, None, {}),
        ],
    },
    "combo.flashback": {
        "name": "Hồi tưởng", "moods": (),
        "steps": [("rewind", 0.0, 1.2, {}), ("sepia", 0.0, 3.0, {}), ("dream", 0.0, 3.0, {}), ("reverb", 0.0, None, {})],
    },
    "combo.fear": {
        "name": "Sợ hãi", "moods": ("fear",),
        "steps": [
            ("flicker", 0.0, 1.5, {}), ("vignette", 0.0, 2.0, {"amount": 0.7}), ("handheld", 0.0, 2.0, {"intensity": 0.3}),
            ("sfx:heartbeat", 0.0, None, {}),
        ],
    },
    "combo.cliffhanger": {
        "name": "Cliffhanger", "moods": (),
        "steps": [
            ("freeze_frame", 0.0, 1.2, {}), ("silence_beat", 0.0, 0.5, {}), ("fade_black", 0.8, 0.8, {}),
            ("continue_card", 0.6, 2.2, {}), ("sfx:stinger_suspense", 0.0, None, {}),
        ],
    },
    "combo.intro_character": {
        "name": "Nhân vật xuất hiện lần đầu", "moods": (),
        "steps": [("freeze_intro", 0.0, 1.8, {}), ("sfx:swish", 0.0, None, {})],
    },
}

STRONG_COMBOS = {"combo.shock", "combo.slap", "combo.anger", "combo.villain", "combo.cliffhanger", "combo.revenge"}

EMOTION_COMBO = {
    "shock": "combo.shock",
    "anger": "combo.anger",
    "sad": "combo.sad",
    "romance": "combo.romance",
    "comedy": "combo.comedy",
    "villain": "combo.villain",
    "fear": "combo.fear",
}


def get(effect_id: str) -> EffectDef | None:
    return EFFECTS.get(effect_id)


def is_known(effect_id: str) -> bool:
    return effect_id in EFFECTS or effect_id in COMBOS


def catalog_for_llm() -> str:
    """Compact catalog text for the LLM planner prompt."""
    lines = []
    by_cat: dict[str, list[EffectDef]] = {}
    for e in EFFECTS.values():
        by_cat.setdefault(e.category, []).append(e)
    for cat, items in by_cat.items():
        lines.append(f"[{cat}]")
        for e in items:
            p = f" params={e.params}" if e.params else ""
            m = f" hợp: {','.join(e.moods)}" if e.moods else ""
            lines.append(f"- {e.id} ({e.strength}, {e.dur}s): {e.desc}{p}{m}")
    lines.append("[combo] (gói nhiều hiệu ứng + tiếng động, dùng như một id)")
    for cid, c in COMBOS.items():
        lines.append(f"- {cid}: {c['name']}")
    lines.append("[caption presets] " + ", ".join(CAPTION_PRESETS))
    return "\n".join(lines)


def to_json() -> dict:
    return {
        "effects": {k: {"category": v.category, "name": v.name, "dur": v.dur, "params": v.params, "anchor": v.anchor}
                    for k, v in EFFECTS.items()},
        "combos": {k: {"name": v["name"]} for k, v in COMBOS.items()},
        "captions": CAPTION_PRESETS,
    }
