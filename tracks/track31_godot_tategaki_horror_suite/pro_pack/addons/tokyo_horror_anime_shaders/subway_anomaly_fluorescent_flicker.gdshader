shader_type canvas_item;
// Japanese Underground Passage ("Exit 8" Style) 50Hz Fluorescent Ballast Flicker & Anomaly Pulse
// Apply to a full-screen ColorRect inside a CanvasLayer.
// Features: Eastern Japan 50Hz AC fluorescent tube hum, magnetic ballast starter stutter,
// cool mercury-vapor green-cyan cast, and radial anomaly dread pulse.
// Author: peco (https://pecopeko.itch.io)

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear;

uniform vec3 fluorescent_tint : source_color = vec3(0.92, 1.00, 0.96);
uniform float hum_50hz_depth : hint_range(0.0, 0.15, 0.005) = 0.025;
uniform float ballast_instability : hint_range(0.0, 1.0, 0.02) = 0.32;
uniform float anomaly_level : hint_range(0.0, 1.0, 0.01) = 0.20;
uniform float corridor_vignette : hint_range(0.0, 1.0, 0.02) = 0.28;

float ballast_hash(float x) {
	return fract(sin(x * 127.1 + 311.7) * 43758.5453123);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 centered = uv * 2.0 - 1.0;
	float radial = dot(centered, centered);

	// Peripheral chromatic shiver that intensifies as anomaly_level rises
	float pulse = 0.5 + 0.5 * sin(TIME * 3.4);
	float ca_offset = anomaly_level * radial * (0.0035 + 0.0025 * pulse);

	float r = texture(screen_texture, clamp(uv + vec2(ca_offset, 0.0), vec2(0.001), vec2(0.999))).r;
	float g = texture(screen_texture, clamp(uv, vec2(0.001), vec2(0.999))).g;
	float b = texture(screen_texture, clamp(uv - vec2(ca_offset, 0.0), vec2(0.001), vec2(0.999))).b;
	vec3 col = vec3(r, g, b);

	// Eastern Japan 50Hz AC tube hum (100Hz optical ripple) + intermittent ballast misfire dips
	float ac_ripple = 1.0 - hum_50hz_depth * (0.5 + 0.5 * sin(TIME * 100.0 * 6.2831853));
	float tick_slot = floor(TIME * 18.0);
	float misfire_rng = ballast_hash(tick_slot);
	float stutter_dip = 1.0;
	if (misfire_rng > (1.0 - ballast_instability * 0.22)) {
		float micro_buzz = ballast_hash(floor(TIME * 95.0));
		stutter_dip = mix(0.52, 0.94, micro_buzz);
	}

	col *= fluorescent_tint * ac_ripple * stutter_dip;

	// Subtle cool underground tile vignette + anomaly peripheral darkening
	float vig = 1.0 - radial * (corridor_vignette + anomaly_level * 0.30) * 0.55;
	col *= clamp(vig, 0.0, 1.0);

	COLOR = vec4(col, 1.0);
}
