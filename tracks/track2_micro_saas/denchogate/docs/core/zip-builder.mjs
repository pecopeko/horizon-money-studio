/**
 * Pure-JS Zero-Dependency PKWARE Stored ZIP (Method 0) Packager.
 *
 * Implements RFC/PKWARE APPNOTE Stored ZIP with:
 * - Accurate IEEE 802.3 CRC-32 table
 * - General Purpose Bit Flag bit 11 (0x0800) for UTF-8 filenames
 *   so Japanese filenames extract cleanly on Windows Explorer & macOS Archive Utility.
 */

const TEXT_ENCODER = new TextEncoder();

const CRC32_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i += 1) {
  let c = i;
  for (let k = 0; k < 8; k += 1) {
    c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  }
  CRC32_TABLE[i] = c >>> 0;
}

/**
 * Compute standard IEEE 802.3 CRC-32 (unsigned 32-bit integer).
 * @param {Uint8Array} bytes
 * @returns {number}
 */
export function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) {
    crc = CRC32_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function toUint8Array(data) {
  if (data instanceof Uint8Array) return data;
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  if (ArrayBuffer.isView(data)) {
    return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  }
  if (typeof data === "string") return TEXT_ENCODER.encode(data);
  throw new TypeError("ZIP entry data must be Uint8Array, ArrayBuffer, TypedArray, or string");
}

function sanitizeZipEntryPath(name) {
  const cleaned = String(name || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter((seg) => seg && seg !== "." && seg !== "..")
    .join("/");
  if (!cleaned) {
    throw new Error("ZIP entry name must be a non-empty valid relative path");
  }
  return cleaned;
}

function toDosDateTime(dateInput) {
  const d =
    dateInput instanceof Date && !Number.isNaN(dateInput.getTime())
      ? dateInput
      : new Date();
  const year = Math.min(2107, Math.max(1980, d.getFullYear()));
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hours = d.getHours();
  const minutes = d.getMinutes();
  const seconds = Math.floor(d.getSeconds() / 2);
  const dosTime = ((hours & 0x1f) << 11) | ((minutes & 0x3f) << 5) | (seconds & 0x1f);
  const dosDate = (((year - 1980) & 0x7f) << 9) | ((month & 0x0f) << 5) | (day & 0x1f);
  return { dosTime, dosDate };
}

const UTF8_FLAG = 0x0800;
const VERSION_NEEDED_STORE = 20;
const VERSION_MADE_BY_UNIX = 0x0314; // Unix (3) + ZIP 2.0 (20)
const UNIX_REGULAR_FILE_ATTR = (0o100644 << 16) >>> 0;

/**
 * Build a valid PKWARE Stored ZIP archive (compression method 0) as a Uint8Array.
 *
 * @param {Array<{ name: string, data: Uint8Array | ArrayBuffer | string, mtime?: Date }>} entries
 * @returns {Uint8Array}
 */
export function buildStoredZip(entries = []) {
  const prepared = [];
  let localSectionSize = 0;
  let centralDirSize = 0;

  for (const entry of entries) {
    const cleanName = sanitizeZipEntryPath(entry.name);
    const nameBytes = TEXT_ENCODER.encode(cleanName);
    const dataBytes = toUint8Array(entry.data);
    const checksum = crc32(dataBytes);
    const { dosTime, dosDate } = toDosDateTime(entry.mtime);

    if (nameBytes.length > 0xffff) {
      throw new Error(`ZIP filename exceeds 65535 bytes: ${cleanName}`);
    }

    const localOffset = localSectionSize;
    localSectionSize += 30 + nameBytes.length + dataBytes.length;
    centralDirSize += 46 + nameBytes.length;

    prepared.push({
      nameBytes,
      dataBytes,
      checksum,
      dosTime,
      dosDate,
      localOffset,
    });
  }

  const totalSize = localSectionSize + centralDirSize + 22;
  const out = new Uint8Array(totalSize);
  const view = new DataView(out.buffer);

  // 1. Write Local File Headers + Payloads
  let offset = 0;
  for (const item of prepared) {
    view.setUint32(offset, 0x04034b50, true); // Local file header signature (PK\x03\x04)
    view.setUint16(offset + 4, VERSION_NEEDED_STORE, true);
    view.setUint16(offset + 6, UTF8_FLAG, true);
    view.setUint16(offset + 8, 0, true); // Compression method 0 = Store
    view.setUint16(offset + 10, item.dosTime, true);
    view.setUint16(offset + 12, item.dosDate, true);
    view.setUint32(offset + 14, item.checksum, true);
    view.setUint32(offset + 18, item.dataBytes.length, true);
    view.setUint32(offset + 22, item.dataBytes.length, true);
    view.setUint16(offset + 26, item.nameBytes.length, true);
    view.setUint16(offset + 28, 0, true); // Extra field length
    out.set(item.nameBytes, offset + 30);
    offset += 30 + item.nameBytes.length;
    out.set(item.dataBytes, offset);
    offset += item.dataBytes.length;
  }

  // 2. Write Central Directory File Headers
  const centralDirOffset = offset;
  for (const item of prepared) {
    view.setUint32(offset, 0x02014b50, true); // Central dir signature (PK\x01\x02)
    view.setUint16(offset + 4, VERSION_MADE_BY_UNIX, true);
    view.setUint16(offset + 6, VERSION_NEEDED_STORE, true);
    view.setUint16(offset + 8, UTF8_FLAG, true);
    view.setUint16(offset + 10, 0, true); // Method 0 = Store
    view.setUint16(offset + 12, item.dosTime, true);
    view.setUint16(offset + 14, item.dosDate, true);
    view.setUint32(offset + 16, item.checksum, true);
    view.setUint32(offset + 20, item.dataBytes.length, true);
    view.setUint32(offset + 24, item.dataBytes.length, true);
    view.setUint16(offset + 28, item.nameBytes.length, true);
    view.setUint16(offset + 30, 0, true); // Extra length
    view.setUint16(offset + 32, 0, true); // Comment length
    view.setUint16(offset + 34, 0, true); // Disk number start
    view.setUint16(offset + 36, 0, true); // Internal file attributes
    view.setUint32(offset + 38, UNIX_REGULAR_FILE_ATTR, true); // External file attributes
    view.setUint32(offset + 42, item.localOffset, true);
    out.set(item.nameBytes, offset + 46);
    offset += 46 + item.nameBytes.length;
  }

  // 3. Write End of Central Directory Record (EOCD)
  view.setUint32(offset, 0x06054b50, true); // EOCD signature (PK\x05\x06)
  view.setUint16(offset + 4, 0, true); // Disk number
  view.setUint16(offset + 6, 0, true); // Disk with central dir
  view.setUint16(offset + 8, prepared.length, true); // Entries on this disk
  view.setUint16(offset + 10, prepared.length, true); // Total entries
  view.setUint32(offset + 12, centralDirSize, true);
  view.setUint32(offset + 16, centralDirOffset, true);
  view.setUint16(offset + 20, 0, true); // Comment length

  return out;
}
