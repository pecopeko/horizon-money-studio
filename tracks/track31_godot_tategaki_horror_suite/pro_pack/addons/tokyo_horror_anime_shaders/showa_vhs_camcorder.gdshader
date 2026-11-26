shader_type canvas_item;
// 1998 Showa VHS Camcorder Post-Process Shader for Godot 4.x
// Apply to a full-screen ColorRect inside a CanvasLayer above your 2D/3D/NVL scene.
// Features: YIQ chroma bleed, bottom VHS head-switching noise band, scanline jitter,
// magnetic tape crease dropouts, CRT scanlines, and analog corner vignette.
// Author: peco (https://pecopeko.itch.io)

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear;

uniform float chroma_bleed_px : hint_range(0.0, 14.0, 0.25) = 4.5;
uniform float scanline_jitter : hint_range(0.0, 0.02, 0.0005) = 0.0022;
uniform float head_switch_height : hint_range(0.0, 0.14, 0.005) = 0.055;
uniform float head_switch_shift : hint_range(0.0, 0.12, 0.005) = 0.042;
uniform float dropout_intensity : hint_range(0.0, 1.0, 0.02) = 0.38;
uniform float scanline_darkness : hint_range(0.0, 0.5, 0.01) = 0.14;
uniform float vignette_strength : hint_range(0.0, 1.0, 0.02) = 0.34;
uniform float time_scale : hint_range(0.0, 3.0, 0.05) = 1.0;

float vhs_hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec3 rgb_to_yiq(vec3 rgb) {
	return vec3(
		dot(rgb, vec3(0.299, 0.587, 0.114)),
		dot(rgb, vec3(0.5959, -0.2746, -0.3213)),
		dot(rgb, vec3(0.2115, -0.5227, 0.3112))
	);
}

vec3 yiq_to_rgb(vec3 yiq) {
	return vec3(
		dot(yiq, vec3(1.0, 0.956, 0.619)),
		dot(yiq, vec3(1.0, -0.272, -0.647)),
		dot(yiq, vec3(1.0, -1.106, 1.703))
	);
}

void fragment() {
	float t = TIME * time_scale;
	vec2 uv = SCREEN_UV;
	float line_id = floor(uv.y * 240.0);

	// 1. Horizontal scanline jitter + slow analog tracking wave
	float line_noise = vhs_hash12(vec2(line_id, floor(t * 29.97))) * 2.0 - 1.0;
	float tracking_wave = sin(uv.y * 9.0 - t * 2.4) * 0.0008;
	uv.x += line_noise * scanline_jitter + tracking_wave;

	// 2. Bottom VHS head-switching tear & static band
	float head_band_start = 1.0 - head_switch_height;
	float head_mask = smoothstep(head_band_start, min(1.0, head_band_start + 0.015), uv.y);
	if (head_mask > 0.001) {
		float tear = (vhs_hash12(vec2(line_id * 1.7, floor(t * 59.94))) - 0.35) * head_switch_shift;
		uv.x += tear * head_mask;
	}

	uv = clamp(uv, vec2(0.001), vec2(0.999));

	// 3. YIQ color-under horizontal chroma smear (sharp Y luma, low-bandwidth I/Q chroma)
	vec2 px_step = vec2(SCREEN_PIXEL_SIZE.x * chroma_bleed_px, 0.0);
	float luma_y = rgb_to_yiq(texture(screen_texture, uv).rgb).x;

	vec3 c0 = rgb_to_yiq(texture(screen_texture, clamp(uv - px_step * 1.5, vec2(0.001), vec2(0.999))).rgb);
	vec3 c1 = rgb_to_yiq(texture(screen_texture, clamp(uv - px_step * 0.5, vec2(0.001), vec2(0.999))).rgb);
	vec3 c2 = rgb_to_yiq(texture(screen_texture, clamp(uv + px_step * 0.6, vec2(0.001), vec2(0.999))).rgb);
	vec3 c3 = rgb_to_yiq(texture(screen_texture, clamp(uv + px_step * 1.8, vec2(0.001), vec2(0.999))).rgb);

	vec2 smeared_iq = (c0.yz * 0.20 + c1.yz * 0.32 + c2.yz * 0.30 + c3.yz * 0.18) * 1.06;
	vec3 col = clamp(yiq_to_rgb(vec3(luma_y, smeared_iq.x, smeared_iq.y)), vec3(0.0), vec3(1.0));

	// 4. Magnetic tape crease / oxide dropout streaks
	float crease_y = fract(t * 0.19);
	float crease_band = smoothstep(0.010, 0.0, abs(uv.y - crease_y));
	float dropout_seed = vhs_hash12(vec2(floor(uv.x * 96.0), line_id + floor(t * 24.0)));
	float dropout_hit = step(0.986 - crease_band * 0.14, dropout_seed) * dropout_intensity;
	col = mix(col, vec3(0.92, 0.94, 0.96), clamp(dropout_hit + head_mask * dropout_seed * 0.35, 0.0, 1.0));

	// 5. Subtle 240p CRT scanlines, warm Showa shadow lift, and corner vignette
	float scan = 1.0 - scanline_darkness * (0.5 + 0.5 * sin(SCREEN_UV.y * 240.0 * 6.2831853));
	col *= scan;
	col = mix(vec3(0.035, 0.030, 0.045), col * vec3(1.02, 0.99, 0.95), 0.96);

	vec2 centered = SCREEN_UV * 2.0 - 1.0;
	float vig = 1.0 - dot(centered, centered) * vignette_strength * 0.55;
	col *= clamp(vig, 0.0, 1.0);

	COLOR = vec4(col, 1.0);
}
