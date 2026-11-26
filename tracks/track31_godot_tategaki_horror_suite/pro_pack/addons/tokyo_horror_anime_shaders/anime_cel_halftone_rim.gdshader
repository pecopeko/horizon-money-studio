shader_type spatial;
render_mode diffuse_toon, specular_toon;
// Anime & Manga 3-Band Cel Shader with Screen-Space Screentone (`網点`) & Rim Light for Godot 4.x
// Apply to any 3D MeshInstance3D / Character mesh via ShaderMaterial.
// Author: peco (https://pecopeko.itch.io)

uniform vec4 albedo_color : source_color = vec4(0.92, 0.90, 0.88, 1.0);
uniform sampler2D albedo_texture : source_color, filter_linear_mipmap;
uniform vec4 mid_shadow_tint : source_color = vec4(0.56, 0.54, 0.66, 1.0);
uniform vec4 deep_shadow_tint : source_color = vec4(0.22, 0.20, 0.32, 1.0);

uniform float lit_threshold : hint_range(-0.5, 0.9, 0.01) = 0.24;
uniform float deep_shadow_threshold : hint_range(-0.9, 0.4, 0.01) = -0.18;

uniform float screentone_density : hint_range(20.0, 240.0, 2.0) = 92.0;
uniform float screentone_angle_deg : hint_range(0.0, 90.0, 1.0) = 22.5;
uniform float screentone_strength : hint_range(0.0, 1.0, 0.02) = 0.65;

uniform vec4 rim_color : source_color = vec4(0.72, 0.92, 1.0, 1.0);
uniform float rim_power : hint_range(0.5, 8.0, 0.1) = 3.2;
uniform float rim_threshold : hint_range(0.1, 0.95, 0.01) = 0.58;
uniform float rim_intensity : hint_range(0.0, 2.0, 0.05) = 0.75;

float manga_halftone_dot(vec2 frag_xy, float density, float angle_deg) {
	float rad = radians(angle_deg);
	mat2 rot = mat2(vec2(cos(rad), -sin(rad)), vec2(sin(rad), cos(rad)));
	vec2 grid_uv = fract((rot * frag_xy) / max(1.0, 800.0 / density)) - vec2(0.5);
	return length(grid_uv) * 1.41421356; // Normalized [0..1] radial distance inside rotated cell
}

void fragment() {
	vec4 tex = texture(albedo_texture, UV);
	ALBEDO = albedo_color.rgb * tex.rgb;
}

void light() {
	float ndotl = dot(NORMAL, LIGHT) * ATTENUATION;

	// 3-band stepped toon diffuse shading + rotated Manga screentone (`網点`) in mid-shadow
	vec3 band_tint = vec3(1.0);
	if (ndotl < deep_shadow_threshold) {
		band_tint = deep_shadow_tint.rgb;
	} else if (ndotl < lit_threshold) {
		float dot_dist = manga_halftone_dot(FRAGCOORD.xy, screentone_density, screentone_angle_deg);
		float band_t = clamp((lit_threshold - ndotl) / max(0.05, lit_threshold - deep_shadow_threshold), 0.0, 1.0);
		float ink_dot = 1.0 - step(band_t * 0.72, dot_dist);
		vec3 dotted_mid = mix(mid_shadow_tint.rgb, deep_shadow_tint.rgb, ink_dot * screentone_strength);
		band_tint = dotted_mid;
	}

	// Crisp stepped Fresnel rim highlight on lit silhouette edge
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), rim_power);
	float rim_mask = step(rim_threshold, fresnel) * smoothstep(-0.2, 0.25, ndotl);
	vec3 rim_term = rim_color.rgb * rim_mask * rim_intensity;

	DIFFUSE_LIGHT += (ALBEDO * band_tint + rim_term) * (LIGHT_COLOR * 0.318309886);
}
