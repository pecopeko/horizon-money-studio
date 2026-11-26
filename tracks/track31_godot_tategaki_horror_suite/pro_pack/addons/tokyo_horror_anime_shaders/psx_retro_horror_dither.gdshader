shader_type canvas_item;
// PS1 / 32-Bit Era Retro Survival Horror Dither & RGB555 Quantizer for Godot 4.x
// Apply to a full-screen ColorRect inside a CanvasLayer.
// Features: Resolution downscale (320x240), exact 4x4 Bayer ordered dithering matrix,
// 15-bit RGB555 color quantization (32 levels/channel), and cold midnight fog tint.
// Author: peco (https://pecopeko.itch.io)

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_nearest;

uniform vec2 target_resolution = vec2(320.0, 240.0);
uniform float color_levels : hint_range(4.0, 64.0, 1.0) = 32.0; // 32 = authentic 5-bit per channel (RGB555)
uniform float dither_strength : hint_range(0.0, 2.0, 0.05) = 0.95;
uniform vec3 fog_tint : source_color = vec3(0.09, 0.14, 0.20);
uniform float fog_shadow_mix : hint_range(0.0, 0.65, 0.01) = 0.18;

float bayer4x4(ivec2 p) {
	int x = p.x & 3;
	int y = p.y & 3;
	int idx = y * 4 + x;
	// Canonical 4x4 Bayer matrix normalized to [-0.5, +0.4375]
	int v = 0;
	if (idx == 0) v = 0;
	else if (idx == 1) v = 8;
	else if (idx == 2) v = 2;
	else if (idx == 3) v = 10;
	else if (idx == 4) v = 12;
	else if (idx == 5) v = 4;
	else if (idx == 6) v = 14;
	else if (idx == 7) v = 6;
	else if (idx == 8) v = 3;
	else if (idx == 9) v = 11;
	else if (idx == 10) v = 1;
	else if (idx == 11) v = 9;
	else if (idx == 12) v = 15;
	else if (idx == 13) v = 7;
	else if (idx == 14) v = 13;
	else v = 5;
	return (float(v) / 16.0) - 0.5;
}

void fragment() {
	vec2 safe_res = max(target_resolution, vec2(64.0, 48.0));
	vec2 pixel_coord = floor(SCREEN_UV * safe_res);
	vec2 snapped_uv = (pixel_coord + vec2(0.5)) / safe_res;

	vec3 col = texture(screen_texture, clamp(snapped_uv, vec2(0.001), vec2(0.999))).rgb;

	// Subtle cold PS1 survival-horror atmospheric tint in dark/mid regions
	float luma = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(col, mix(fog_tint, col, 0.65), (1.0 - smoothstep(0.0, 0.65, luma)) * fog_shadow_mix);

	// Apply 4x4 Bayer ordered dither prior to RGB555 quantization
	float bayer_offset = bayer4x4(ivec2(int(pixel_coord.x), int(pixel_coord.y)));
	float quant_max = max(color_levels - 1.0, 1.0);
	vec3 dithered = col + (bayer_offset * dither_strength) / quant_max;
	vec3 quantized = floor(clamp(dithered, vec3(0.0), vec3(1.0)) * quant_max + vec3(0.5)) / quant_max;

	COLOR = vec4(quantized, 1.0);
}
