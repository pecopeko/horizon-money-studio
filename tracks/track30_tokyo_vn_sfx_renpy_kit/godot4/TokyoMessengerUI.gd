class_name TokyoMessengerUI
extends Control
## Drop-in Godot 4.x Tokyo Smartphone Messenger ('Kidoku' / LINE-Style) Overlay.
##
## Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
## License: Commercial Royalty-Free (Included in Tokyo VN SFX & Messenger Pro)
##
## Usage:
##   var phone := TokyoMessengerUI.new()
##   add_child(phone)
##   await phone.receive_message("水瀬 葵", phone.jp_ruby("放課後", "ほうかご") + "またね！", "17:16")
##   var pick := await phone.prompt_choices([
##       {"id": "gate", "text": "今すぐ校門に向かうよ！"},
##       {"id": "konbini", "text": "コンビニ寄ってから行く！"}
##   ])

signal choice_selected(choice_id: String, choice_text: String)
signal message_received(sender: String, body: String)
signal message_read(timestamp: String)

@export_dir var sfx_root_dir: String = "res://audio/tokyo_sfx"
@export var room_title: String = "水瀬 葵 (Aoi)"
@export var room_subtitle: String = "Online · Tokyo"
@export var read_receipt_text: String = "既読"
@export var show_furigana: bool = true
@export var phone_size: Vector2 = Vector2(420.0, 740.0)

const SFX_REL_PATHS := {
	"kidoku_pop": "05_vn_messenger_and_jrpg_ui/25_messenger_kidoku_pop.wav",
	"send_swoosh": "05_vn_messenger_and_jrpg_ui/26_messenger_send_swoosh.wav",
	"sticker_bounce": "05_vn_messenger_and_jrpg_ui/27_messenger_sticker_bounce.wav",
	"typing_tick": "05_vn_messenger_and_jrpg_ui/28_messenger_typing_tick.wav",
	"desk_vibrate": "05_vn_messenger_and_jrpg_ui/29_smartphone_desk_vibrate.wav",
	"hover": "05_vn_messenger_and_jrpg_ui/34_ui_choice_hover_soft.wav",
	"confirm": "05_vn_messenger_and_jrpg_ui/35_ui_confirm_sparkle.wav",
	"affection_up": "05_vn_messenger_and_jrpg_ui/38_vn_affection_up_chime.wav",
}

var _phone_frame: PanelContainer
var _title_label: Label
var _subtitle_label: Label
var _clock_label: Label
var _furigana_btn: Button
var _scroll: ScrollContainer
var _feed_vbox: VBoxContainer
var _typing_row: HBoxContainer
var _typing_dots_label: Label
var _choices_panel: PanelContainer
var _choices_vbox: VBoxContainer
var _sfx_players: Array[AudioStreamPlayer] = []
var _sfx_cursor: int = 0
var _typing_accum: float = 0.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_PASS
	_init_sfx_pool(4)
	_build_phone_shell()


func _process(delta: float) -> void:
	if _typing_row != null and _typing_row.visible:
		_typing_accum += delta
		var step := int(_typing_accum * 3.2) % 3
		if step == 0:
			_typing_dots_label.text = "● · ·"
		elif step == 1:
			_typing_dots_label.text = "· ● ·"
		else:
			_typing_dots_label.text = "· · ●"


## Format kanji + furigana for Godot 4 RichTextLabel (BBCode mode).
func jp_ruby(kanji: String, reading: String) -> String:
	if not show_furigana or reading.is_empty():
		return kanji
	return "%s[font_size=11][color=#8FA6C4](%s)[/color][/font_size]" % [kanji, reading]


## Play a named SFX from the 40-WAV Tokyo SFX kit if loaded in the project.
func play_sfx(sfx_key: String, volume_db: float = -2.0) -> void:
	if _sfx_players.is_empty():
		return
	var rel_path: String = SFX_REL_PATHS.get(sfx_key, sfx_key)
	var full_path := sfx_root_dir.path_join(rel_path)
	if not ResourceLoader.exists(full_path):
		return
	var stream := load(full_path) as AudioStream
	if stream == null:
		return
	var player := _sfx_players[_sfx_cursor % _sfx_players.size()]
	_sfx_cursor += 1
	player.stream = stream
	player.volume_db = volume_db
	player.play()


## Insert a centered date or location divider chip into the conversation feed.
func add_divider(label_text: String) -> void:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	var chip := PanelContainer.new()
	chip.add_theme_stylebox_override("panel", _make_box(Color("#222B3A"), 10, 10, 4))
	var lbl := Label.new()
	lbl.text = label_text
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", Color("#9AA9C0"))
	chip.add_child(lbl)
	row.add_child(chip)
	_feed_vbox.add_child(row)
	_scroll_to_bottom_deferred()


## Show animated '...' typing indicator, then append an incoming NPC chat bubble.
func receive_message(
	sender: String,
	body_bbcode: String,
	timestamp: String = "23:42",
	typing_sec: float = 0.75,
	avatar_monogram: String = "葵",
	avatar_color: Color = Color("#3A6EA5")
) -> void:
	_clock_label.text = timestamp
	if typing_sec > 0.0:
		_typing_row.visible = true
		_feed_vbox.move_child(_typing_row, _feed_vbox.get_child_count() - 1)
		_scroll_to_bottom_deferred()
		play_sfx("typing_tick", -6.0)
		await get_tree().create_timer(typing_sec * 0.5).timeout
		play_sfx("typing_tick", -6.0)
		await get_tree().create_timer(typing_sec * 0.5).timeout
		_typing_row.visible = false

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)

	var avatar := PanelContainer.new()
	avatar.custom_minimum_size = Vector2(34.0, 34.0)
	avatar.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	avatar.add_theme_stylebox_override("panel", _make_box(avatar_color, 17, 0, 0))
	var av_lbl := Label.new()
	av_lbl.text = avatar_monogram
	av_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	av_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	av_lbl.add_theme_font_size_override("font_size", 15)
	av_lbl.add_theme_color_override("font_color", Color.WHITE)
	avatar.add_child(av_lbl)
	row.add_child(avatar)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 2)
	if not sender.is_empty():
		var s_lbl := Label.new()
		s_lbl.text = sender
		s_lbl.add_theme_font_size_override("font_size", 11)
		s_lbl.add_theme_color_override("font_color", Color("#93A3BA"))
		col.add_child(s_lbl)

	var bubble_line := HBoxContainer.new()
	bubble_line.add_theme_constant_override("separation", 6)

	var bubble := PanelContainer.new()
	bubble.add_theme_stylebox_override("panel", _make_box(Color("#253042"), 12, 12, 9))
	var rich := _make_rich_body(body_bbcode, Color("#EEF3FA"), 245.0)
	bubble.add_child(rich)
	bubble_line.add_child(bubble)

	var ts_lbl := Label.new()
	ts_lbl.text = timestamp
	ts_lbl.size_flags_vertical = Control.SIZE_SHRINK_END
	ts_lbl.add_theme_font_size_override("font_size", 10)
	ts_lbl.add_theme_color_override("font_color", Color("#7C8CA3"))
	bubble_line.add_child(ts_lbl)

	col.add_child(bubble_line)
	row.add_child(col)
	_feed_vbox.add_child(row)
	_feed_vbox.move_child(_typing_row, _feed_vbox.get_child_count() - 1)

	play_sfx("kidoku_pop")
	message_received.emit(sender, body_bbcode)
	_scroll_to_bottom_deferred()


## Append an outgoing player LINE-green bubble and flip '既読' ('Read') receipt ON.
func send_player_message(
	body_bbcode: String,
	timestamp: String = "23:42",
	mark_kidoku: bool = true,
	kidoku_delay_sec: float = 0.45
) -> void:
	_clock_label.text = timestamp
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 6)

	var meta_col := VBoxContainer.new()
	meta_col.alignment = BoxContainer.ALIGNMENT_END
	meta_col.add_theme_constant_override("separation", 1)

	var kidoku_lbl := Label.new()
	kidoku_lbl.text = read_receipt_text
	kidoku_lbl.visible = false
	kidoku_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	kidoku_lbl.add_theme_font_size_override("font_size", 10)
	kidoku_lbl.add_theme_color_override("font_color", Color("#87CA7A"))
	meta_col.add_child(kidoku_lbl)

	var ts_lbl := Label.new()
	ts_lbl.text = timestamp
	ts_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	ts_lbl.add_theme_font_size_override("font_size", 10)
	ts_lbl.add_theme_color_override("font_color", Color("#7C8CA3"))
	meta_col.add_child(ts_lbl)

	var bubble := PanelContainer.new()
	bubble.add_theme_stylebox_override("panel", _make_box(Color("#7AD64E"), 12, 12, 9))
	var rich := _make_rich_body(body_bbcode, Color("#121912"), 245.0)
	bubble.add_child(rich)

	row.add_child(meta_col)
	row.add_child(bubble)
	_feed_vbox.add_child(row)
	_feed_vbox.move_child(_typing_row, _feed_vbox.get_child_count() - 1)

	play_sfx("send_swoosh")
	_scroll_to_bottom_deferred()

	if mark_kidoku:
		if kidoku_delay_sec > 0.0:
			await get_tree().create_timer(kidoku_delay_sec).timeout
		kidoku_lbl.text = read_receipt_text
		kidoku_lbl.visible = true
		play_sfx("kidoku_pop", -4.0)
		message_read.emit(timestamp)


## Send an expressive Tokyo sticker ('Stamp') card with bounce SFX.
func send_sticker(glyph: String, caption: String, timestamp: String = "23:43") -> void:
	var body := "[center][font_size=26]%s[/font_size]\n[b]%s[/b][/center]" % [glyph, caption]
	play_sfx("sticker_bounce")
	await send_player_message(body, timestamp, true, 0.35)


## Display branching player reply buttons and await selection.
## Each dictionary in `options` expects `{"id": String, "text": String}`.
func prompt_choices(
	options: Array[Dictionary],
	auto_send_reply: bool = true,
	timestamp: String = "23:42"
) -> String:
	for child in _choices_vbox.get_children():
		child.queue_free()

	var header := Label.new()
	header.text = "Select Reply / 返信を選択"
	header.add_theme_font_size_override("font_size", 11)
	header.add_theme_color_override("font_color", Color("#8FA1B8"))
	_choices_vbox.add_child(header)

	for opt in options:
		var opt_id := String(opt.get("id", ""))
		var opt_text := String(opt.get("text", ""))
		var btn := Button.new()
		btn.text = opt_text
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		btn.add_theme_font_size_override("font_size", 14)
		btn.add_theme_color_override("font_color", Color("#EFF4FC"))
		btn.add_theme_stylebox_override("normal", _make_box(Color("#253146"), 8, 12, 8))
		btn.add_theme_stylebox_override("hover", _make_box(Color("#324360"), 8, 12, 8))
		btn.add_theme_stylebox_override("pressed", _make_box(Color("#3D5378"), 8, 12, 8))
		btn.mouse_entered.connect(func() -> void: play_sfx("hover", -6.0))
		btn.pressed.connect(func() -> void: choice_selected.emit(opt_id, opt_text))
		_choices_vbox.add_child(btn)

	_choices_panel.visible = true
	_scroll_to_bottom_deferred()

	var result: Array = await choice_selected
	var chosen_id := String(result[0])
	var chosen_text := String(result[1])
	_choices_panel.visible = false

	if auto_send_reply and not chosen_text.is_empty():
		await send_player_message(chosen_text, timestamp)
	return chosen_id


## Optional self-contained playable showcase scene.
func run_demo_conversation() -> void:
	add_divider("Today · After School (放課後)")
	var opening := jp_ruby("放課後", "ほうかご") + "のチャイム鳴ったね！" + jp_ruby("神保町", "じんぼうちょう") + "の古本屋、寄っていく？"
	await receive_message("水瀬 葵", opening, "17:16", 0.8)
	var pick := await prompt_choices(
		[
			{"id": "gate", "text": "今すぐ校門に向かうよ！"},
			{"id": "konbini", "text": "駅前コンビニで肉まん買って待ってて！"},
		],
		true,
		"17:17"
	)
	if pick == "gate":
		play_sfx("affection_up")
		await receive_message("水瀬 葵", "やった！じゃあ踏切の前で待ってるね。", "17:17", 0.7)
	else:
		await receive_message("水瀬 葵", "賛成！あたたかいお茶も買っておくね。", "17:18", 0.7)
	await send_sticker("★彡", "On My Way! / 今行くよ！", "17:18")


# -----------------------------------------------------------------------------
# Internal UI Builders
# -----------------------------------------------------------------------------

func _init_sfx_pool(voice_count: int) -> void:
	for i in range(voice_count):
		var p := AudioStreamPlayer.new()
		p.name = "TokyoSfxVoice_%d" % i
		add_child(p)
		_sfx_players.append(p)


func _build_phone_shell() -> void:
	_phone_frame = PanelContainer.new()
	_phone_frame.custom_minimum_size = phone_size
	_phone_frame.size = phone_size
	_phone_frame.anchor_left = 1.0
	_phone_frame.anchor_right = 1.0
	_phone_frame.anchor_top = 0.5
	_phone_frame.anchor_bottom = 0.5
	_phone_frame.offset_left = -phone_size.x - 36.0
	_phone_frame.offset_right = -36.0
	_phone_frame.offset_top = -phone_size.y * 0.5
	_phone_frame.offset_bottom = phone_size.y * 0.5
	_phone_frame.add_theme_stylebox_override("panel", _make_box(Color("#11151D"), 22, 12, 12))
	add_child(_phone_frame)

	var root_vbox := VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 0)
	_phone_frame.add_child(root_vbox)

	# Status Bar
	var status_bar := PanelContainer.new()
	status_bar.add_theme_stylebox_override("panel", _make_box(Color("#181E29"), 10, 12, 5))
	var status_hbox := HBoxContainer.new()
	_clock_label = Label.new()
	_clock_label.text = "23:42"
	_clock_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_clock_label.add_theme_font_size_override("font_size", 12)
	_clock_label.add_theme_color_override("font_color", Color("#C7D2E2"))
	var sig_lbl := Label.new()
	sig_lbl.text = "5G · 94%"
	sig_lbl.add_theme_font_size_override("font_size", 11)
	sig_lbl.add_theme_color_override("font_color", Color("#8E9CB2"))
	status_hbox.add_child(_clock_label)
	status_hbox.add_child(sig_lbl)
	status_bar.add_child(status_hbox)
	root_vbox.add_child(status_bar)

	# Room Header
	var header_bar := PanelContainer.new()
	header_bar.add_theme_stylebox_override("panel", _make_box(Color("#1F2735"), 0, 14, 9))
	var header_hbox := HBoxContainer.new()
	header_hbox.add_theme_constant_override("separation", 10)
	var title_col := VBoxContainer.new()
	title_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_col.add_theme_constant_override("separation", 1)
	_title_label = Label.new()
	_title_label.text = room_title
	_title_label.add_theme_font_size_override("font_size", 16)
	_title_label.add_theme_color_override("font_color", Color("#F3F6FB"))
	_subtitle_label = Label.new()
	_subtitle_label.text = room_subtitle
	_subtitle_label.add_theme_font_size_override("font_size", 11)
	_subtitle_label.add_theme_color_override("font_color", Color("#6BD65A"))
	title_col.add_child(_title_label)
	title_col.add_child(_subtitle_label)

	_furigana_btn = Button.new()
	_furigana_btn.text = "ふりがな ON" if show_furigana else "ふりがな OFF"
	_furigana_btn.add_theme_font_size_override("font_size", 11)
	_furigana_btn.pressed.connect(func() -> void:
		show_furigana = not show_furigana
		_furigana_btn.text = "ふりがな ON" if show_furigana else "ふりがな OFF"
	)
	header_hbox.add_child(title_col)
	header_hbox.add_child(_furigana_btn)
	header_bar.add_child(header_hbox)
	root_vbox.add_child(header_bar)

	# Scrollable Chat Feed
	var feed_bg := PanelContainer.new()
	feed_bg.size_flags_vertical = Control.SIZE_EXPAND_FILL
	feed_bg.add_theme_stylebox_override("panel", _make_box(Color("#151A24"), 0, 12, 12))
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_feed_vbox = VBoxContainer.new()
	_feed_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_feed_vbox.add_theme_constant_override("separation", 10)
	_scroll.add_child(_feed_vbox)
	feed_bg.add_child(_scroll)
	root_vbox.add_child(feed_bg)

	# Animated Typing Row (hidden until receive_message)
	_typing_row = HBoxContainer.new()
	_typing_row.visible = false
	var typing_pill := PanelContainer.new()
	typing_pill.add_theme_stylebox_override("panel", _make_box(Color("#253042"), 12, 14, 8))
	_typing_dots_label = Label.new()
	_typing_dots_label.text = "● · ·"
	_typing_dots_label.add_theme_font_size_override("font_size", 13)
	_typing_dots_label.add_theme_color_override("font_color", Color("#A4B6D0"))
	typing_pill.add_child(_typing_dots_label)
	_typing_row.add_child(typing_pill)
	_feed_vbox.add_child(_typing_row)

	# Bottom Reply Choice Drawer
	_choices_panel = PanelContainer.new()
	_choices_panel.visible = false
	_choices_panel.add_theme_stylebox_override("panel", _make_box(Color("#1B2230"), 10, 10, 10))
	_choices_vbox = VBoxContainer.new()
	_choices_vbox.add_theme_constant_override("separation", 6)
	_choices_panel.add_child(_choices_vbox)
	root_vbox.add_child(_choices_panel)


func _make_rich_body(bbcode_text: String, text_color: Color, max_w: float) -> RichTextLabel:
	var rich := RichTextLabel.new()
	rich.bbcode_enabled = true
	rich.fit_content = true
	rich.scroll_active = false
	rich.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	rich.custom_minimum_size = Vector2(min(max_w, max(96.0, float(bbcode_text.length()) * 14.0)), 0.0)
	rich.add_theme_font_size_override("normal_font_size", 14)
	rich.add_theme_color_override("default_color", text_color)
	rich.text = bbcode_text
	return rich


func _make_box(bg: Color, radius: int, pad_x: int, pad_y: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.corner_radius_top_left = radius
	sb.corner_radius_top_right = radius
	sb.corner_radius_bottom_left = radius
	sb.corner_radius_bottom_right = radius
	sb.content_margin_left = float(pad_x)
	sb.content_margin_right = float(pad_x)
	sb.content_margin_top = float(pad_y)
	sb.content_margin_bottom = float(pad_y)
	return sb


func _scroll_to_bottom_deferred() -> void:
	await get_tree().process_frame
	if _scroll != null and _scroll.get_v_scroll_bar() != null:
		_scroll.scroll_vertical = int(_scroll.get_v_scroll_bar().max_value)
