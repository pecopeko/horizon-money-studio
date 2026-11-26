@tool
class_name TategakiNovelBox
extends Control
## Godot 4 Japanese Vertical Text ("Tategaki" / 縦書き) & Furigana ("Ruby" / ルビ) Control Node.
##
## Built for Japanese Visual Novels (NVL Sound Novels like Higurashi / Kamaitachi),
## Manga speech balloons (フキダシ), shrine plaques, and underground anomaly signage.
##
## Features:
## - Right-to-left vertical column flow (縦書き)
## - Authentic JIS X 4051 Kinsoku Shori (行頭禁則 + 行末禁則 + 追い出し/ぶら下がり)
## - Vertical CJK punctuation rotation (ー … 〜 「」『』（）) & small-kana upper-right shift (っゃゅょ)
## - Tate-Chu-Yoko (縦中横) upright horizontal numbers/marks (8, 24, !?, !!, [tcy]8番[/tcy])
## - Right-margin Furigana / Ruby via Aozora/Narou (`｜東京《とうきょう》`, `漢字《かんじ》`) or `[ruby=...]...[/ruby]`
## - Typewriter reveal with punctuation pause multiplier and `character_revealed` audio signal
##
## Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
## License: MIT

signal character_revealed(character: String, char_index: int)
signal reveal_finished()

const KINSOKU_HEAD := "。、，．・：；？！ー～」』）］｝〉》】〕〗〙〛ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ々ゝゞー〜…‥！？!?,.:;)]}"
const KINSOKU_TAIL := "「『（［｛〈《【〔〖〘〚([“‘"
const ROTATE_90_CW := "ー−―—–〜～…‥＝：；「」『』（）()［］[]｛｝{}〈〉《》【】〔〕→←"
const SHIFT_TOP_RIGHT := "。、，．"
const SHIFT_SMALL_KANA := "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ"

@export_group("Text & Ruby Markup")
@export_multiline var novel_text: String = "「｜東京《とうきょう》の[tcy]8番[/tcy]｜地下通路《ちかつうろ》で、｜異変《いへん》を｜見《み》つけたら——すぐに｜引《ひ》き｜返《かえ》すこと！？」":
	set(value):
		novel_text = value
		_rebuild_layout()
		queue_redraw()

@export var enable_kinsoku: bool = true:
	set(value):
		enable_kinsoku = value
		_rebuild_layout()
		queue_redraw()

@export var enable_tate_chu_yoko: bool = true:
	set(value):
		enable_tate_chu_yoko = value
		_rebuild_layout()
		queue_redraw()

@export_group("Typography & Metrics")
@export var custom_font: Font:
	set(value):
		custom_font = value
		_rebuild_layout()
		queue_redraw()

@export_range(12, 96, 1) var font_size: int = 28:
	set(value):
		font_size = value
		_rebuild_layout()
		queue_redraw()

@export_range(0.30, 0.70, 0.01) var ruby_scale: float = 0.45:
	set(value):
		ruby_scale = value
		queue_redraw()

@export_range(1.00, 1.80, 0.02) var line_height_ratio: float = 1.14:
	set(value):
		line_height_ratio = value
		_rebuild_layout()
		queue_redraw()

@export_range(1.35, 3.20, 0.05) var column_spacing_ratio: float = 1.90:
	set(value):
		column_spacing_ratio = value
		_rebuild_layout()
		queue_redraw()

@export var box_padding: Vector2 = Vector2(28.0, 26.0):
	set(value):
		box_padding = value
		_rebuild_layout()
		queue_redraw()

@export_group("Colors & Backdrop")
@export var text_color: Color = Color(0.95, 0.94, 0.90, 1.0):
	set(value):
		text_color = value
		queue_redraw()

@export var ruby_color: Color = Color(0.56, 0.85, 0.98, 0.96):
	set(value):
		ruby_color = value
		queue_redraw()

@export var shadow_color: Color = Color(0.0, 0.0, 0.0, 0.68):
	set(value):
		shadow_color = value
		queue_redraw()

@export var shadow_offset: Vector2 = Vector2(1.5, 1.5):
	set(value):
		shadow_offset = value
		queue_redraw()

@export var draw_panel_backdrop: bool = true:
	set(value):
		draw_panel_backdrop = value
		queue_redraw()

@export var panel_color: Color = Color(0.04, 0.06, 0.12, 0.84):
	set(value):
		panel_color = value
		queue_redraw()

@export var panel_border_color: Color = Color(0.88, 0.25, 0.25, 0.55):
	set(value):
		panel_border_color = value
		queue_redraw()

@export_group("Typewriter Reveal")
## -1 displays all characters immediately; >= 0 limits revealed base characters.
@export var visible_characters: int = -1:
	set(value):
		visible_characters = value
		queue_redraw()

@export_range(1.0, 120.0, 0.5) var chars_per_second: float = 22.0
@export_range(1.0, 10.0, 0.25) var punctuation_pause_multiplier: float = 4.5
@export_range(1.0, 6.0, 0.25) var comma_pause_multiplier: float = 2.2
@export var show_page_cursor: bool = true

var _columns: Array = []
var _total_base_chars: int = 0
var _is_revealing: bool = false
var _reveal_timer: float = 0.0
var _cursor_blink_time: float = 0.0


func _ready() -> void:
	if custom_minimum_size == Vector2.ZERO:
		custom_minimum_size = Vector2(360.0, 280.0)
	_rebuild_layout()
	resized.connect(_on_resized)


func _on_resized() -> void:
	_rebuild_layout()
	queue_redraw()


func _process(delta: float) -> void:
	_cursor_blink_time += delta
	if _is_revealing:
		_step_typewriter(delta)
	elif show_page_cursor and not Engine.is_editor_hint():
		queue_redraw()


## Sets new Japanese vertical text and optionally begins typewriter reveal from 0.
func set_novel_text(new_text: String, auto_start_typewriter: bool = true) -> void:
	novel_text = new_text
	if auto_start_typewriter:
		start_typewriter()
	else:
		visible_characters = -1
		_is_revealing = false


## Starts character-by-character Sound Novel reveal from the first glyph.
func start_typewriter() -> void:
	_rebuild_layout()
	visible_characters = 0
	_reveal_timer = 0.0
	_is_revealing = _total_base_chars > 0
	if not _is_revealing:
		reveal_finished.emit()
	queue_redraw()


## Immediately reveals the entire text block.
func skip_to_end() -> void:
	_is_revealing = false
	visible_characters = -1
	reveal_finished.emit()
	queue_redraw()


## Clears text and stops typewriter playback.
func clear_text() -> void:
	_is_revealing = false
	novel_text = ""
	visible_characters = -1


func is_typewriter_active() -> bool:
	return _is_revealing


func get_total_character_count() -> int:
	return _total_base_chars


func _step_typewriter(delta: float) -> void:
	if visible_characters < 0 or visible_characters >= _total_base_chars:
		_is_revealing = false
		visible_characters = -1
		reveal_finished.emit()
		queue_redraw()
		return

	_reveal_timer += delta * chars_per_second
	while _reveal_timer >= 1.0 and _is_revealing:
		var revealed_ch: String = _get_base_char_at(visible_characters)
		visible_characters += 1
		_reveal_timer -= _pause_weight_for_char(revealed_ch)
		character_revealed.emit(revealed_ch, visible_characters - 1)
		if visible_characters >= _total_base_chars:
			_is_revealing = false
			visible_characters = -1
			reveal_finished.emit()
			break
	queue_redraw()


func _pause_weight_for_char(ch: String) -> float:
	if ch == "。" or ch == "！" or ch == "？" or ch == "!" or ch == "?" or ch == "…":
		return punctuation_pause_multiplier
	if ch == "、" or ch == "，" or ch == "」" or ch == "』" or ch == "—":
		return comma_pause_multiplier
	return 1.0


func _get_active_font() -> Font:
	if custom_font != null:
		return custom_font
	return get_theme_default_font()


static func _is_kanji_codepoint(cp: int) -> bool:
	return (
		(cp >= 0x4E00 and cp <= 0x9FFF)
		or (cp >= 0x3400 and cp <= 0x4DBF)
		or cp == 0x3005 # 々
		or cp == 0x30F6 # ヶ
		or cp == 0x30F5 # ヵ
		or cp == 0x3006 # 〆
		or cp == 0x3007 # 〇
	)


static func _is_ascii_digit(ch: String) -> bool:
	if ch.is_empty():
		return false
	var cp: int = ch.unicode_at(0)
	return cp >= 0x30 and cp <= 0x39


static func _make_unit(kind: String, text_val: String, ruby_val: String = "", span_val: int = 1) -> Dictionary:
	var is_head: bool = false
	var is_tail: bool = false
	if kind != "newline" and not text_val.is_empty():
		if kind == "tcy" and (text_val == "!?" or text_val == "?!" or text_val == "!!" or text_val == "??"):
			is_head = true
		elif KINSOKU_HEAD.contains(text_val.substr(0, 1)):
			is_head = true
		if KINSOKU_TAIL.contains(text_val.substr(text_val.length() - 1, 1)):
			is_tail = true
	return {
		"kind": kind,
		"text": text_val,
		"ruby": ruby_val,
		"cell_span": span_val,
		"is_head": is_head,
		"is_tail": is_tail,
	}


## Parses Japanese text with Aozora/Narou `｜東京《とうきょう》`, implicit `漢字《かんじ》`,
## BBCode `[ruby=とうきょう]東京[/ruby]`, and Tate-Chu-Yoko (`24`, `!?`, `[tcy]8番[/tcy]`).
static func parse_units(raw_text: String, allow_tcy: bool = true) -> Array:
	var src: String = raw_text.replace("\r\n", "\n").replace("\r", "\n")
	var n: int = src.length()
	var units: Array = []
	var i: int = 0

	while i < n:
		var ch: String = src.substr(i, 1)

		if ch == "\n":
			units.append(_make_unit("newline", "\n", "", 0))
			i += 1
			continue

		# 1. BBCode [ruby=reading]base[/ruby]
		if src.substr(i, 6) == "[ruby=":
			var close_bracket: int = src.find("]", i + 6)
			var end_tag: int = src.find("[/ruby]", close_bracket + 1) if close_bracket != -1 else -1
			if close_bracket != -1 and end_tag != -1:
				var reading: String = src.substr(i + 6, close_bracket - (i + 6)).trim_prefix("\"").trim_suffix("\"")
				var base_txt: String = src.substr(close_bracket + 1, end_tag - (close_bracket + 1))
				if not base_txt.is_empty():
					units.append(_make_unit("ruby", base_txt, reading, maxi(1, base_txt.length())))
				i = end_tag + 7
				continue

		# 2. Explicit [tcy]...[/tcy]
		if src.substr(i, 5) == "[tcy]":
			var end_tcy: int = src.find("[/tcy]", i + 5)
			if end_tcy != -1:
				var tcy_txt: String = src.substr(i + 5, end_tcy - (i + 5))
				if not tcy_txt.is_empty():
					units.append(_make_unit("tcy", tcy_txt, "", 1))
				i = end_tcy + 6
				continue

		# 3. Explicit Aozora/Narou pipe: ｜東京《とうきょう》 or |東京《とうきょう》
		if ch == "｜" or ch == "|":
			var open_rb: int = src.find("《", i + 1)
			var next_nl: int = src.find("\n", i + 1)
			if open_rb != -1 and (next_nl == -1 or open_rb < next_nl):
				var close_rb: int = src.find("》", open_rb + 1)
				if close_rb != -1 and (next_nl == -1 or close_rb < next_nl):
					var p_base: String = src.substr(i + 1, open_rb - (i + 1))
					var p_ruby: String = src.substr(open_rb + 1, close_rb - (open_rb + 1))
					if not p_base.is_empty():
						units.append(_make_unit("ruby", p_base, p_ruby, maxi(1, p_base.length())))
						i = close_rb + 1
						continue

		# 4. Implicit Aozora Kanji ruby: 漢字《かんじ》
		if ch == "《" and not units.is_empty():
			var close_imp: int = src.find("》", i + 1)
			var next_nl2: int = src.find("\n", i + 1)
			if close_imp != -1 and (next_nl2 == -1 or close_imp < next_nl2):
				var kanji_buf: String = ""
				while not units.is_empty():
					var last_u: Dictionary = units.back()
					if last_u["kind"] == "char" and _is_kanji_codepoint(String(last_u["text"]).unicode_at(0)):
						kanji_buf = String(last_u["text"]) + kanji_buf
						units.pop_back()
					else:
						break
				if not kanji_buf.is_empty():
					var imp_ruby: String = src.substr(i + 1, close_imp - (i + 1))
					units.append(_make_unit("ruby", kanji_buf, imp_ruby, kanji_buf.length()))
					i = close_imp + 1
					continue

		# 5. Automatic Tate-Chu-Yoko (1-2 ASCII digits or !? / ?! / !! / ??)
		if allow_tcy:
			if _is_ascii_digit(ch):
				var d_end: int = i
				while d_end < n and _is_ascii_digit(src.substr(d_end, 1)):
					d_end += 1
				var d_len: int = d_end - i
				if d_len <= 2:
					units.append(_make_unit("tcy", src.substr(i, d_len), "", 1))
					i = d_end
					continue
				else:
					while i < d_end:
						units.append(_make_unit("char", src.substr(i, 1), "", 1))
						i += 1
					continue

			if i + 1 < n:
				var pair: String = src.substr(i, 2)
				if pair == "!?" or pair == "?!" or pair == "!!" or pair == "??":
					units.append(_make_unit("tcy", pair, "", 1))
					i += 2
					continue

		units.append(_make_unit("char", ch, "", 1))
		i += 1

	return units


static func _col_cells(col: Array) -> int:
	var total: int = 0
	for u in col:
		total += int(u["cell_span"])
	return total


## Wraps parsed units into vertical columns respecting JIS X 4051 Kinsoku Shori.
static func layout_columns(units: Array, max_cells_per_col: int, use_kinsoku: bool = true) -> Array:
	var safe_max: int = maxi(1, max_cells_per_col)
	var columns: Array = []
	var current_col: Array = []

	for unit in units:
		if unit["kind"] == "newline":
			columns.append(current_col)
			current_col = []
			continue

		var projected: int = _col_cells(current_col) + int(unit["cell_span"])
		if projected <= safe_max:
			current_col.append(unit)
			continue

		if not use_kinsoku or current_col.is_empty():
			columns.append(current_col)
			current_col = [unit]
			continue

		var buf: Array = current_col.duplicate()
		buf.append(unit)
		var valid_split: int = -1
		for k in range(buf.size() - 1, 0, -1):
			var prefix: Array = buf.slice(0, k)
			if _col_cells(prefix) > safe_max:
				continue
			if bool(buf[k - 1]["is_tail"]):
				continue
			if bool(buf[k]["is_head"]):
				continue
			valid_split = k
			break

		if valid_split != -1:
			columns.append(buf.slice(0, valid_split))
			current_col = buf.slice(valid_split, buf.size())
		else:
			if bool(unit["is_head"]):
				current_col.append(unit)
			else:
				columns.append(current_col)
				current_col = [unit]

	if not current_col.is_empty() or columns.is_empty():
		columns.append(current_col)
	return columns


func _rebuild_layout() -> void:
	var box_h: float = maxf(size.y, custom_minimum_size.y)
	var cell_step: float = float(font_size) * line_height_ratio
	var usable_h: float = maxf(cell_step, box_h - box_padding.y * 2.0)
	var max_cells: int = maxi(1, int(floor(usable_h / cell_step)))

	var units: Array = parse_units(novel_text, enable_tate_chu_yoko)
	_columns = layout_columns(units, max_cells, enable_kinsoku)

	_total_base_chars = 0
	for col in _columns:
		for u in col:
			_total_base_chars += maxi(1, String(u["text"]).length())


func _get_base_char_at(target_idx: int) -> String:
	var cursor: int = 0
	for col in _columns:
		for u in col:
			var txt: String = String(u["text"])
			var step_len: int = maxi(1, txt.length())
			if target_idx < cursor + step_len:
				var local_i: int = clampi(target_idx - cursor, 0, txt.length() - 1)
				return txt.substr(local_i, 1)
			cursor += step_len
	return ""


func _draw() -> void:
	if draw_panel_backdrop:
		draw_rect(Rect2(Vector2.ZERO, size), panel_color, true)
		draw_rect(Rect2(Vector2.ZERO, size), panel_border_color, false, 1.5)

	var font: Font = _get_active_font()
	if font == null:
		return

	var fsize: int = font_size
	var rsize: int = maxi(9, int(round(float(fsize) * ruby_scale)))
	var cell_step: float = float(fsize) * line_height_ratio
	var col_step: float = float(fsize) * column_spacing_ratio
	var rightmost_cx: float = size.x - box_padding.x - float(fsize) * 0.85

	var char_budget: int = _total_base_chars if visible_characters < 0 else visible_characters
	var drawn_count: int = 0
	var last_glyph_bottom := Vector2(rightmost_cx, box_padding.y)

	for col_idx in range(_columns.size()):
		var col: Array = _columns[col_idx]
		var col_cx: float = rightmost_cx - float(col_idx) * col_step
		if col_cx < box_padding.x * 0.35:
			break

		var row_cursor: int = 0
		for u in col:
			if drawn_count >= char_budget:
				break

			var kind: String = String(u["kind"])
			var txt: String = String(u["text"])
			var span: int = int(u["cell_span"])
			var y_top: float = box_padding.y + float(row_cursor) * cell_step

			if kind == "tcy":
				_draw_tcy_cell(font, txt, Vector2(col_cx, y_top + cell_step * 0.5), fsize, text_color)
				drawn_count += maxi(1, txt.length())
				last_glyph_bottom = Vector2(col_cx, y_top + cell_step)
			elif kind == "ruby":
				var visible_slice_len: int = mini(txt.length(), char_budget - drawn_count)
				for b_i in range(visible_slice_len):
					var b_ch: String = txt.substr(b_i, 1)
					var cell_center := Vector2(col_cx, y_top + (float(b_i) + 0.5) * cell_step)
					_draw_vertical_char(font, b_ch, cell_center, fsize, text_color)
					last_glyph_bottom = Vector2(col_cx, y_top + float(b_i + 1) * cell_step)

				var ruby_txt: String = String(u["ruby"])
				if not ruby_txt.is_empty() and visible_slice_len > 0:
					var ruby_reveal_ratio: float = float(visible_slice_len) / float(maxi(1, txt.length()))
					var ruby_vis_count: int = maxi(1, int(ceil(float(ruby_txt.length()) * ruby_reveal_ratio)))
					_draw_ruby_run(
						font,
						ruby_txt.substr(0, ruby_vis_count),
						ruby_txt.length(),
						col_cx + float(fsize) * 0.54 + float(rsize) * 0.52,
						y_top,
						float(span) * cell_step,
						rsize,
						ruby_color
					)
				drawn_count += visible_slice_len
			else:
				var cell_center := Vector2(col_cx, y_top + cell_step * 0.5)
				_draw_vertical_char(font, txt, cell_center, fsize, text_color)
				drawn_count += 1
				last_glyph_bottom = Vector2(col_cx, y_top + cell_step)

			row_cursor += span

		if drawn_count >= char_budget:
			break

	# Blinking Sound Novel page-wait indicator when reveal is complete
	if show_page_cursor and not _is_revealing and _total_base_chars > 0:
		var pulse: float = 0.5 + 0.5 * sin(_cursor_blink_time * 5.2)
		var tri_c := Color(panel_border_color.r, panel_border_color.g, panel_border_color.b, 0.35 + 0.60 * pulse)
		var tip := last_glyph_bottom + Vector2(0.0, float(fsize) * 0.48)
		var hw: float = float(fsize) * 0.24
		var pts := PackedVector2Array([
			tip + Vector2(-hw, -hw * 1.1),
			tip + Vector2(hw, -hw * 1.1),
			tip + Vector2(0.0, hw * 0.35),
		])
		draw_colored_polygon(pts, tri_c)


func _draw_vertical_char(font: Font, ch: String, cell_center: Vector2, sz: int, col: Color) -> void:
	var gsize: Vector2 = font.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sz)
	var ascent: float = font.get_ascent(sz)

	if ROTATE_90_CW.contains(ch):
		draw_set_transform(cell_center, PI * 0.5, Vector2.ONE)
		var local_pos := Vector2(-gsize.x * 0.5, -gsize.y * 0.5 + ascent)
		if shadow_color.a > 0.0:
			draw_string(font, local_pos + Vector2(shadow_offset.y, -shadow_offset.x), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, shadow_color)
		draw_string(font, local_pos, ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, col)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		return

	var shift := Vector2.ZERO
	if SHIFT_TOP_RIGHT.contains(ch):
		shift = Vector2(float(sz) * 0.30, -float(sz) * 0.28)
	elif SHIFT_SMALL_KANA.contains(ch):
		shift = Vector2(float(sz) * 0.11, -float(sz) * 0.09)

	var draw_pos := Vector2(cell_center.x - gsize.x * 0.5, cell_center.y - gsize.y * 0.5 + ascent) + shift
	if shadow_color.a > 0.0:
		draw_string(font, draw_pos + shadow_offset, ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, shadow_color)
	draw_string(font, draw_pos, ch, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, col)


func _draw_tcy_cell(font: Font, txt: String, cell_center: Vector2, sz: int, col: Color) -> void:
	var scale_x: float = 0.76 if txt.length() >= 2 else 1.0
	var scale_y: float = 0.88 if txt.length() >= 2 else 1.0
	var gsize: Vector2 = font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, sz)
	var ascent: float = font.get_ascent(sz)

	draw_set_transform(cell_center, 0.0, Vector2(scale_x, scale_y))
	var local_pos := Vector2(-gsize.x * 0.5, -gsize.y * 0.5 + ascent)
	if shadow_color.a > 0.0:
		draw_string(font, local_pos + shadow_offset, txt, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, shadow_color)
	draw_string(font, local_pos, txt, HORIZONTAL_ALIGNMENT_LEFT, -1, sz, col)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _draw_ruby_run(
	font: Font,
	vis_ruby: String,
	total_ruby_len: int,
	ruby_cx: float,
	span_top_y: float,
	span_height: float,
	rsize: int,
	col: Color
) -> void:
	var r_step: float = float(rsize) * 1.04
	var natural_h: float = float(total_ruby_len) * r_step
	var start_y: float = span_top_y + (span_height - natural_h) * 0.5
	if total_ruby_len > 1 and natural_h < span_height * 0.72:
		r_step = (span_height * 0.80) / float(total_ruby_len)
		start_y = span_top_y + (span_height - r_step * float(total_ruby_len)) * 0.5

	for idx in range(vis_ruby.length()):
		var r_ch: String = vis_ruby.substr(idx, 1)
		var r_center := Vector2(ruby_cx, start_y + (float(idx) + 0.5) * r_step)
		_draw_vertical_char(font, r_ch, r_center, rsize, col)
