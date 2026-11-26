@tool
extends EditorPlugin

const BALLOON_NODE := "MangaFukidashiBalloon"
const BALLOON_SCRIPT := "res://addons/tokyo_horror_anime_shaders/MangaFukidashiBalloon.gd"
const BALLOON_ICON := "res://addons/tokyo_horror_anime_shaders/MangaFukidashiBalloon.svg"


func _enter_tree() -> void:
	var script_res: Script = load(BALLOON_SCRIPT)
	var icon_res: Texture2D = load(BALLOON_ICON)
	add_custom_type(BALLOON_NODE, "Control", script_res, icon_res)


func _exit_tree() -> void:
	remove_custom_type(BALLOON_NODE)
