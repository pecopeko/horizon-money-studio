@tool
class_name MangaFukidashiBalloon
extends Control
## Procedural Japanese Manga Speech Balloon (`フキダシ`) with embedded `TategakiNovelBox`.
##
## Supports 4 classic Japanese comic / visual-novel balloon silhouettes:
## - `ROUND` (`丸フキダシ`): Crisp vertical oval dialogue balloon + directional speech tail
## - `SHOUT_BURST` (`叫びウニフラッシュ`): High-impact radial spike burst for shock / climax lines
## - `THOUGHT_CLOUD` (`心の声モコモコ`): Scalloped cloud contour + trailing thought bubbles
## - `HORROR_JAGGED` (`怨念ギザギザ`): Trembling asymmetric dark-bordered dread balloon
##
## Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)

enum BalloonStyle {
	ROUND = 0,
	SHOUT_BURST = 1,
	THOUGHT_CLOUD = 2,
	HORROR_JAGGED = 3,
}

@export var balloon_style: BalloonStyle = BalloonStyle.ROUND:
	set(value):
		balloon_style = value
		_sync_child_box()
		queue_redraw()

@export_multiline var dialogue_text: String = "「まさか……\n[tcy]8番[/tcy]の｜案内板《あんないばん》が\n｜動《うご》いた！？」":
	set(value):
		dialogue_text = value
		_sync_child_box()
		queue_redraw()

@export var fill_color: Color = Color(0.98, 0.97, 0.94, 0.98):
	set(value):
		fill_color = value
		queue_redraw()

@export var stroke_color: Color = Color(0.07, 0.09, 0.14, 1.0):
	set(value):
		stroke_color = value
		queue_redraw()

@export_range(1.0, 10.0, 0.5) var stroke_width: float = 3.0:
	set(value):
		stroke_width = value
		queue_redraw()

@export var text_ink_color: Color = Color(0.08, 0.09, 0.13, 1.0):
	set(value):
		text_ink_color = value
		_sync_child_box()

@export var ruby_ink_color: Color = Color(0.78, 0.16, 0.18, 1.0):
	set(value):
		ruby_ink_color = value
		_sync_child_box()

@export_range(14, 64, 1) var font_size: int = 24:
	set(value):
		font_size = value
		_sync_child_box()

@export var tail_offset: Vector2 = Vector2(-42.0, 36.0):
	set(value):
		tail_offset = value
		queue_redraw()

@export_range(12, 64, 2) var burst_spike_count: int = 28:
	set(value):
		burst_spike_count = value
		queue_redraw()

@export_range(0.05, 0.35, 0.01) var burst_depth_ratio: float = 0.17:
	set(value):
		burst_depth_ratio = value
		_sync_child_box()
		queue_redraw()

@export var inner_margin: Vector2 = Vector2(44.0, 38.0):
	set(value):
		inner_margin = value
		_sync_child_box()
		queue_redraw()

var _tategaki_box: TategakiNovelBox


func _ready() -> void:
	if custom_minimum_size == Vector2.ZERO:
		custom_minimum_size = Vector2(260.0, 320.0)
	_ensure_child_box()
	_sync_child_box()
	resized.connect(_on_resized)


func _on_resized() -> void:
	_sync_child_box()
	queue_redraw()


func get_tategaki_box() -> TategakiNovelBox:
	_ensure_child_box()
	return _tategaki_box


func _ensure_child_box() -> void:
	if _tategaki_box != null and is_instance_valid(_tategaki_box):
		return
	for child in get_children():
		if child is TategakiNovelBox:
			_tategaki_box = child
			return
	_tategaki_box = TategakiNovelBox.new()
	_tategaki_box.name = "BalloonTategakiBox"
	_tategaki_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_tategaki_box)


func _sync_child_box() -> void:
	_ensure_child_box()
	if _tategaki_box == null:
		return
	var pad_scale: float = 1.18 if balloon_style == BalloonStyle.SHOUT_BURST else 1.0
	var mx: float = inner_margin.x * pad_scale
	var my: float = inner_margin.y * pad_scale
	_tategaki_box.position = Vector2(mx, my)
	_tategaki_box.size = Vector2(maxf(64.0, size.x - mx * 2.0), maxf(64.0, size.y - my * 2.0))
	_tategaki_box.draw_panel_backdrop = false
	_tategaki_box.shadow_color = Color(0.0, 0.0, 0.0, 0.0)
	_tategaki_box.text_color = text_ink_color
	_tategaki_box.ruby_color = ruby_ink_color
	_tategaki_box.font_size = font_size
	_tategaki_box.box_padding = Vector2(8.0, 8.0)
	_tategaki_box.show_page_cursor = false
	_tategaki_box.novel_text = dialogue_text


func _draw() -> void:
	var center: Vector2 = size * 0.5
	var rx: float = maxf(24.0, size.x * 0.5 - stroke_width * 2.0 - 8.0)
	var ry: float = maxf(24.0, size.y * 0.5 - stroke_width * 2.0 - 8.0)

	match balloon_style:
		BalloonStyle.ROUND:
			_draw_round_balloon(center, rx, ry)
		BalloonStyle.SHOUT_BURST:
			_draw_shout_burst(center, rx, ry)
		BalloonStyle.THOUGHT_CLOUD:
			_draw_thought_cloud(center, rx, ry)
		BalloonStyle.HORROR_JAGGED:
			_draw_horror_jagged(center, rx, ry)


func _draw_round_balloon(center: Vector2, rx: float, ry: float) -> void:
	# Speech pointer triangle anchored near bottom-left/right toward tail_offset
	var tail_dir: Vector2 = tail_offset.normalized() if tail_offset.length_squared() > 0.01 else Vector2(-0.6, 0.8)
	var anchor := Vector2(center.x + tail_dir.x * rx * 0.72, center.y + tail_dir.y * ry * 0.78)
	var tip: Vector2 = anchor + tail_offset
	var tangent := Vector2(-tail_dir.y, tail_dir.x) * 13.0
	var tail_poly := PackedVector2Array([anchor - tangent, tip, anchor + tangent])

	# Draw outer stroke on tail first, then body ellipse, then inner fills for seamless union
	draw_polyline(PackedVector2Array([anchor - tangent, tip, anchor + tangent]), stroke_color, stroke_width * 1.6, true)

	var segs: int = 72
	var pts := PackedVector2Array()
	var closed_pts := PackedVector2Array()
	for i in range(segs):
		var ang: float = TAU * float(i) / float(segs)
		var p := Vector2(center.x + cos(ang) * rx, center.y + sin(ang) * ry)
		pts.append(p)
		closed_pts.append(p)
	closed_pts.append(pts[0])

	draw_colored_polygon(pts, fill_color)
	draw_polyline(closed_pts, stroke_color, stroke_width, true)
	draw_colored_polygon(tail_poly, fill_color)


func _draw_shout_burst(center: Vector2, rx: float, ry: float) -> void:
	var spikes: int = maxi(12, burst_spike_count)
	var total_verts: int = spikes * 2
	var pts := PackedVector2Array()
	var closed_pts := PackedVector2Array()

	for i in range(total_verts):
		var ang: float = TAU * float(i) / float(total_verts)
		var is_tip: bool = (i % 2) == 0
		var jitter: float = 0.04 * sin(float(i) * 3.7)
		var r_mult: float = (1.0 + jitter) if is_tip else (1.0 - burst_depth_ratio)
		var p := Vector2(center.x + cos(ang) * rx * r_mult, center.y + sin(ang) * ry * r_mult)
		pts.append(p)
		closed_pts.append(p)
	closed_pts.append(pts[0])

	draw_colored_polygon(pts, fill_color)
	draw_polyline(closed_pts, stroke_color, stroke_width, true)


func _draw_thought_cloud(center: Vector2, rx: float, ry: float) -> void:
	var puffs: int = 16
	var sub_steps: int = 8
	var pts := PackedVector2Array()
	var closed_pts := PackedVector2Array()
	var lobe_amp: float = minf(rx, ry) * 0.10

	var total: int = puffs * sub_steps
	for i in range(total):
		var t: float = float(i) / float(total)
		var ang: float = TAU * t
		var scallop: float = absf(sin(ang * float(puffs) * 0.5)) * lobe_amp
		var p := Vector2(
			center.x + cos(ang) * (rx * 0.90 + scallop),
			center.y + sin(ang) * (ry * 0.90 + scallop)
		)
		pts.append(p)
		closed_pts.append(p)
	closed_pts.append(pts[0])

	draw_colored_polygon(pts, fill_color)
	draw_polyline(closed_pts, stroke_color, stroke_width, true)

	# Trailing thought bubbles ("モコモコ")
	var tail_dir: Vector2 = tail_offset.normalized() if tail_offset.length_squared() > 0.01 else Vector2(-0.6, 0.8)
	var b1: Vector2 = Vector2(center.x + tail_dir.x * rx * 0.92, center.y + tail_dir.y * ry * 0.92) + tail_offset * 0.38
	var b2: Vector2 = b1 + tail_offset * 0.45
	draw_circle(b1, 9.5, stroke_color)
	draw_circle(b1, 9.5 - stroke_width * 0.8, fill_color)
	draw_circle(b2, 5.5, stroke_color)
	draw_circle(b2, 5.5 - stroke_width * 0.8, fill_color)


func _draw_horror_jagged(center: Vector2, rx: float, ry: float) -> void:
	var segs: int = 96
	var pts := PackedVector2Array()
	var closed_pts := PackedVector2Array()
	for i in range(segs):
		var ang: float = TAU * float(i) / float(segs)
		var tremor: float = 1.0 - 0.065 * absf(sin(float(i) * 5.3 + cos(float(i) * 2.1)))
		var p := Vector2(center.x + cos(ang) * rx * tremor, center.y + sin(ang) * ry * tremor)
		pts.append(p)
		closed_pts.append(p)
	closed_pts.append(pts[0])

	draw_colored_polygon(pts, fill_color)
	draw_polyline(closed_pts, stroke_color, stroke_width * 1.35, true)
