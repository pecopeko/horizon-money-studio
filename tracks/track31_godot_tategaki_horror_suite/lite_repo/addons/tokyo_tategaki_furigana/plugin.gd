@tool
extends EditorPlugin

const NODE_NAME := "TategakiNovelBox"
const SCRIPT_PATH := "res://addons/tokyo_tategaki_furigana/TategakiNovelBox.gd"
const ICON_PATH := "res://addons/tokyo_tategaki_furigana/TategakiNovelBox.svg"


func _enter_tree() -> void:
	var script_res: Script = load(SCRIPT_PATH)
	var icon_res: Texture2D = load(ICON_PATH)
	add_custom_type(NODE_NAME, "Control", script_res, icon_res)


func _exit_tree() -> void:
	remove_custom_type(NODE_NAME)
