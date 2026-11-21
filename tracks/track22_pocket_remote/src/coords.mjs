/**
 * Pure viewport coordinate mapping & clamping utilities for PocketBridge.
 * Maps iPhone Safari touch/click client coordinates (including pinch-zoomed or
 * scrolled image bounding rects) into exact logical browser viewport pixels.
 */

export const DEFAULT_VIEWPORT = Object.freeze({
  width: 1280,
  height: 900,
});

/**
 * Clamp a numeric value into [min, max].
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
export function clamp(value, min, max) {
  if (!Number.isFinite(value)) {
    throw new TypeError(`Expected finite number, got ${String(value)}`);
  }
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/**
 * Clamp logical (x, y) coordinates safely inside [0, viewportWidth - 1] x [0, viewportHeight - 1].
 * @param {object} params
 * @param {number} params.x
 * @param {number} params.y
 * @param {number} [params.viewportWidth=1280]
 * @param {number} [params.viewportHeight=900]
 * @returns {{ x: number, y: number }}
 */
export function clampViewportPoint({
  x,
  y,
  viewportWidth = DEFAULT_VIEWPORT.width,
  viewportHeight = DEFAULT_VIEWPORT.height,
}) {
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) {
    throw new RangeError(`Invalid viewportWidth: ${String(viewportWidth)}`);
  }
  if (!Number.isFinite(viewportHeight) || viewportHeight <= 0) {
    throw new RangeError(`Invalid viewportHeight: ${String(viewportHeight)}`);
  }
  return {
    x: clamp(Math.round(Number(x)), 0, Math.floor(viewportWidth) - 1),
    y: clamp(Math.round(Number(y)), 0, Math.floor(viewportHeight) - 1),
  };
}

/**
 * Convert an iPhone touch/mouse (clientX, clientY) event and current rendered
 * element getBoundingClientRect() ({ left, top, width, height }) into exact
 * clamped logical viewport coordinates.
 *
 * Works identically under 1x fit-to-width, CSS container zoom/pan, and iOS
 * Safari pinch-zoom because clientX/clientY and getBoundingClientRect() share
 * the same client coordinate frame.
 *
 * @param {object} params
 * @param {number} params.clientX
 * @param {number} params.clientY
 * @param {{ left: number, top: number, width: number, height: number }} params.rect
 * @param {number} [params.viewportWidth=1280]
 * @param {number} [params.viewportHeight=900]
 * @returns {{ x: number, y: number, ratioX: number, ratioY: number }}
 */
export function mapClientPointToViewport({
  clientX,
  clientY,
  rect,
  viewportWidth = DEFAULT_VIEWPORT.width,
  viewportHeight = DEFAULT_VIEWPORT.height,
}) {
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) {
    throw new TypeError("clientX and clientY must be finite numbers");
  }
  if (
    !rect ||
    typeof rect !== "object" ||
    !Number.isFinite(rect.left) ||
    !Number.isFinite(rect.top) ||
    !Number.isFinite(rect.width) ||
    !Number.isFinite(rect.height) ||
    rect.width <= 0 ||
    rect.height <= 0
  ) {
    throw new RangeError("rect must have positive finite width and height");
  }

  const rawRatioX = (clientX - rect.left) / rect.width;
  const rawRatioY = (clientY - rect.top) / rect.height;
  const ratioX = clamp(rawRatioX, 0, 1);
  const ratioY = clamp(rawRatioY, 0, 1);

  const rawX = ratioX * viewportWidth;
  const rawY = ratioY * viewportHeight;

  const clamped = clampViewportPoint({
    x: rawX,
    y: rawY,
    viewportWidth,
    viewportHeight,
  });

  return {
    x: clamped.x,
    y: clamped.y,
    ratioX,
    ratioY,
  };
}
