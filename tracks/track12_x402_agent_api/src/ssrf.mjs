/**
 * Strict SSRF protection and bounded public-web fetch utilities (pure Web Standards).
 * Works identically in Cloudflare Workers V8 isolates and Node.js 20+.
 */

const FORBIDDEN_HOSTS = new Set([
  "localhost",
  "localhost.localdomain",
  "ip6-localhost",
  "ip6-loopback",
  "metadata.google.internal",
  "metadata.goog",
  "metadata",
  "instance-data",
  "metadata.azure.internal",
  "169.254.169.254",
  "169.254.170.2",
  "fd00:ec2::254",
]);

const FORBIDDEN_SUFFIXES = [
  ".local",
  ".internal",
  ".localhost",
  ".home.arpa",
  ".localdomain",
  ".corp",
  ".lan",
];

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);

export class SSRFError extends Error {
  constructor(message) {
    super(message);
    this.name = "SSRFError";
    this.code = "SSRF_BLOCKED";
    this.httpStatus = 403;
  }
}

/**
 * Parse a dotted-quad or numeric/hex/octal IPv4 literal into 4 octets, or return null if not an IPv4 literal.
 */
function parseIpv4Literal(rawHost) {
  const host = rawHost.toLowerCase();
  // Pure numeric (e.g. 2130706433) or hex (0x7f000001) or octal (0177.0.0.1) or dotted parts
  const parts = host.split(".");
  if (parts.length === 0 || parts.length > 4) return null;
  if (!parts.every((p) => /^(?:0x[0-9a-f]+|0[0-7]*|[1-9][0-9]*|0)$/.test(p))) {
    return null;
  }

  const nums = parts.map((p) => {
    if (p.startsWith("0x")) return Number.parseInt(p.slice(2), 16);
    if (p.length > 1 && p.startsWith("0")) return Number.parseInt(p, 8);
    return Number.parseInt(p, 10);
  });
  if (nums.some((n) => !Number.isFinite(n) || n < 0)) return null;

  let value = 0;
  if (nums.length === 1) {
    if (nums[0] > 0xffffffff) return null;
    value = nums[0];
  } else if (nums.length === 2) {
    if (nums[0] > 0xff || nums[1] > 0xffffff) return null;
    value = (nums[0] * 0x1000000) + nums[1];
  } else if (nums.length === 3) {
    if (nums[0] > 0xff || nums[1] > 0xff || nums[2] > 0xffff) return null;
    value = (nums[0] * 0x1000000) + (nums[1] * 0x10000) + nums[2];
  } else {
    if (nums.some((n) => n > 0xff)) return null;
    value = (nums[0] * 0x1000000) + (nums[1] * 0x10000) + (nums[2] * 0x100) + nums[3];
  }

  return [
    (value >>> 24) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 8) & 0xff,
    value & 0xff,
  ];
}

export function isPublicIpv4Octets([a, b, c]) {
  if (a === 0) return false; // 0.0.0.0/8 "this network"
  if (a === 10) return false; // 10.0.0.0/8 RFC1918
  if (a === 100 && b >= 64 && b <= 127) return false; // 100.64.0.0/10 CGNAT
  if (a === 127) return false; // 127.0.0.0/8 loopback
  if (a === 169 && b === 254) return false; // 169.254.0.0/16 link-local & cloud metadata
  if (a === 172 && b >= 16 && b <= 31) return false; // 172.16.0.0/12 RFC1918
  if (a === 192 && b === 0 && c === 0) return false; // 192.0.0.0/24 IETF protocol assignments
  if (a === 192 && b === 0 && c === 2) return false; // 192.0.2.0/24 TEST-NET-1
  if (a === 192 && b === 88 && c === 99) return false; // 192.88.99.0/24 6to4 relay
  if (a === 192 && b === 168) return false; // 192.168.0.0/16 RFC1918
  if (a === 198 && (b === 18 || b === 19)) return false; // 198.18.0.0/15 benchmarking
  if (a === 198 && b === 51 && c === 100) return false; // 198.51.100.0/24 TEST-NET-2
  if (a === 203 && b === 0 && c === 113) return false; // 203.0.113.0/24 TEST-NET-3
  if (a >= 224) return false; // 224.0.0.0/4 multicast + 240.0.0.0/4 reserved + broadcast
  return true;
}

/**
 * Expand an IPv6 literal into 8 16-bit groups, or return null if invalid.
 */
function parseIpv6Groups(rawHost) {
  let host = rawHost.toLowerCase();
  if (host.startsWith("[") && host.endsWith("]")) {
    host = host.slice(1, -1);
  }
  const zoneIdx = host.indexOf("%");
  if (zoneIdx !== -1) host = host.slice(0, zoneIdx);
  if (!host.includes(":")) return null;

  // Handle embedded IPv4 suffix (e.g. ::ffff:127.0.0.1)
  const lastColon = host.lastIndexOf(":");
  const tail = host.slice(lastColon + 1);
  if (tail.includes(".")) {
    const v4 = parseIpv4Literal(tail);
    if (!v4) return null;
    const hi = ((v4[0] << 8) | v4[1]).toString(16);
    const lo = ((v4[2] << 8) | v4[3]).toString(16);
    host = `${host.slice(0, lastColon)}:${hi}:${lo}`;
  }

  const dbl = host.split("::");
  if (dbl.length > 2) return null;
  const left = dbl[0] ? dbl[0].split(":") : [];
  const right = dbl.length === 2 && dbl[1] ? dbl[1].split(":") : [];
  const missing = 8 - (left.length + right.length);
  if (dbl.length === 1 && missing !== 0) return null;
  if (dbl.length === 2 && missing < 0) return null;

  const full = [...left, ...Array(Math.max(0, missing)).fill("0"), ...right];
  if (full.length !== 8) return null;
  const groups = [];
  for (const part of full) {
    if (!/^[0-9a-f]{1,4}$/.test(part)) return null;
    groups.push(Number.parseInt(part, 16));
  }
  return groups;
}

export function isPublicIpv6Groups(g) {
  // Unspecified :: or loopback ::1
  const firstSevenZero = g.slice(0, 7).every((x) => x === 0);
  if (firstSevenZero && (g[7] === 0 || g[7] === 1)) return false;

  // IPv4-mapped ::ffff:a.b.c.d or IPv4-compatible ::a.b.c.d
  if (g[0] === 0 && g[1] === 0 && g[2] === 0 && g[3] === 0 && g[4] === 0 && (g[5] === 0xffff || g[5] === 0)) {
    const octets = [g[6] >>> 8, g[6] & 0xff, g[7] >>> 8, g[7] & 0xff];
    return isPublicIpv4Octets(octets);
  }
  // NAT64 well-known prefix 64:ff9b::/96
  if (g[0] === 0x0064 && g[1] === 0xff9b && g[2] === 0 && g[3] === 0 && g[4] === 0 && g[5] === 0) {
    const octets = [g[6] >>> 8, g[6] & 0xff, g[7] >>> 8, g[7] & 0xff];
    return isPublicIpv4Octets(octets);
  }

  const hi = g[0];
  if ((hi & 0xfe00) === 0xfc00) return false; // fc00::/7 Unique Local (ULA)
  if ((hi & 0xffc0) === 0xfe80) return false; // fe80::/10 Link-local
  if ((hi & 0xffc0) === 0xfec0) return false; // fec0::/10 Site-local (deprecated)
  if ((hi & 0xff00) === 0xff00) return false; // ff00::/8 Multicast
  if (hi === 0x2001 && g[1] === 0x0db8) return false; // 2001:db8::/32 documentation
  if (hi === 0x0100 && g[1] === 0 && g[2] === 0 && g[3] === 0) return false; // discard-only
  return true;
}

/**
 * Validate an external HTTP(S) URL against strict SSRF policy.
 * Returns normalized URL string or throws SSRFError.
 */
export function assertSafePublicUrl(rawUrl) {
  const input = String(rawUrl ?? "").trim();
  if (!input) {
    throw new SSRFError("URL must not be empty.");
  }
  if (/[\u0000-\u001f\u007f]/.test(input)) {
    throw new SSRFError("URL contains forbidden control characters.");
  }

  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    throw new SSRFError(`Invalid HTTP(S) URL: ${input}`);
  }

  const protocol = parsed.protocol.toLowerCase();
  if (protocol !== "http:" && protocol !== "https:") {
    throw new SSRFError(`Unsupported URL scheme "${protocol}". Only http: and https: are allowed.`);
  }
  if (parsed.username || parsed.password) {
    throw new SSRFError("Embedded URL credentials are forbidden.");
  }

  const rawHost = parsed.hostname.toLowerCase().replace(/\.+$/, "");
  if (!rawHost) {
    throw new SSRFError("URL must include a hostname.");
  }
  if (FORBIDDEN_HOSTS.has(rawHost) || FORBIDDEN_SUFFIXES.some((s) => rawHost.endsWith(s))) {
    throw new SSRFError(`Blocked local, internal, or metadata host: "${rawHost}".`);
  }

  // Check IPv6 literal
  if (rawHost.includes(":") || (rawHost.startsWith("[") && rawHost.endsWith("]"))) {
    const groups = parseIpv6Groups(rawHost);
    if (!groups || !isPublicIpv6Groups(groups)) {
      throw new SSRFError(`Blocked non-public IPv6 address: "${rawHost}".`);
    }
    return parsed.toString();
  }

  // Check IPv4 literal (dotted, integer, hex, octal)
  const v4 = parseIpv4Literal(rawHost);
  if (v4) {
    if (!isPublicIpv4Octets(v4)) {
      throw new SSRFError(`Blocked non-public IPv4 address: "${rawHost}" (${v4.join(".")}).`);
    }
    return parsed.toString();
  }

  // Require at least one dot in public DNS hostnames (blocks bare internal hostnames like "redis", "db", "metadata")
  if (!rawHost.includes(".") || !/^[a-z0-9.-]+$/.test(rawHost)) {
    throw new SSRFError(`Blocked non-public or invalid DNS hostname: "${rawHost}".`);
  }

  return parsed.toString();
}

/**
 * Perform an SSRF-checked HTTP GET with manual redirect hop validation and hard timeout.
 */
export async function safePublicFetch(
  rawUrl,
  {
    fetchImpl = fetch,
    headers = {},
    maxRedirects = 4,
    timeoutMs = 10000,
    method = "GET",
  } = {},
) {
  let currentUrl = assertSafePublicUrl(rawUrl);
  const redirectChain = [];

  for (let hop = 0; hop <= maxRedirects; hop += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response;
    try {
      response = await fetchImpl(currentUrl, {
        method,
        headers,
        redirect: "manual",
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }

    if (REDIRECT_STATUSES.has(response.status)) {
      const location = (response.headers.get("location") || "").trim();
      if (!location) {
        return { response, finalUrl: currentUrl, redirectChain };
      }
      if (hop >= maxRedirects) {
        throw new Error(`Exceeded maximum redirect hops (${maxRedirects}) for ${rawUrl}`);
      }
      const nextUrl = assertSafePublicUrl(new URL(location, currentUrl).toString());
      redirectChain.push({ status: response.status, from: currentUrl, to: nextUrl });
      currentUrl = nextUrl;
      continue;
    }

    return { response, finalUrl: currentUrl, redirectChain };
  }

  throw new Error(`Exceeded maximum redirect hops (${maxRedirects}) for ${rawUrl}`);
}

/**
 * Read a bounded UTF-8 text preview from a Response stream without blowing Worker memory.
 */
export async function readBoundedText(response, maxBytes = 262144) {
  if (!response.body || typeof response.body.getReader !== "function") {
    const text = await response.text();
    return text.slice(0, maxBytes);
  }
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (total < maxBytes) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value) {
        const remaining = maxBytes - total;
        chunks.push(value.byteLength > remaining ? value.subarray(0, remaining) : value);
        total += Math.min(value.byteLength, remaining);
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Ignore cancel errors on closed streams
    }
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: false }).decode(merged);
}
