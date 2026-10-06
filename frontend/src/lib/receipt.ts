/**
 * Client-side receipt preparation.
 *
 * Volunteers photograph receipts on a phone, where one JPEG is routinely 3-5 MB
 * — several times the server's per-file cap, and slow to upload over mobile
 * data. Downscaling to a generous long edge and re-encoding as JPEG keeps a
 * perfectly legible receipt at a few hundred KB, so the server cap
 * (`MAX_UPLOAD_SIZE_MB`) becomes a backstop rather than the thing a normal
 * submission trips over.
 *
 * PDFs — and anything the browser cannot decode — are returned untouched; the
 * server still enforces the size and type limits.
 */

/** Longest edge, in pixels, a receipt image is scaled down to. */
const MAX_EDGE = 2000;

/** JPEG quality for the re-encode — receipts stay readable well below 1. */
const QUALITY = 0.82;

/** Skip the (lossy) round-trip when the file is already this small. */
const SKIP_BELOW_BYTES = 400 * 1024;

/** Only these can be re-encoded in the canvas; a PDF passes straight through. */
const RESIZABLE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

export async function prepareReceipt(file: File): Promise<File> {
  if (!RESIZABLE_TYPES.has(file.type) || file.size <= SKIP_BELOW_BYTES) {
    return file;
  }

  const loaded = await loadImage(file);
  if (!loaded) return file;

  try {
    const { width, height } = fitWithin(loaded.width, loaded.height, MAX_EDGE);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(loaded.source, 0, 0, width, height);

    const blob = await toBlob(canvas, "image/jpeg", QUALITY);
    // Never hand back something larger than the file we started with.
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], withJpegExtension(file.name), {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
  } catch {
    // Any decode/encode failure is non-fatal: upload the original and let the
    // server's own size/type checks answer.
    return file;
  } finally {
    loaded.release();
  }
}

type LoadedImage = {
  source: CanvasImageSource;
  width: number;
  height: number;
  release: () => void;
};

async function loadImage(file: File): Promise<LoadedImage | null> {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file);
      return {
        source: bitmap,
        width: bitmap.width,
        height: bitmap.height,
        release: () => bitmap.close(),
      };
    } catch {
      /* fall through to the <img> path */
    }
  }

  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("unreadable image"));
      image.src = url;
    });
  } catch {
    URL.revokeObjectURL(url);
    return null;
  }
  return {
    source: image,
    width: image.naturalWidth,
    height: image.naturalHeight,
    release: () => URL.revokeObjectURL(url),
  };
}

function fitWithin(width: number, height: number, max: number) {
  if (width <= max && height <= max) return { width, height };
  const scale = max / Math.max(width, height);
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

function toBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number
): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

function withJpegExtension(name: string): string {
  const base = name.replace(/\.[^./\\]+$/, "");
  return `${base || "receipt"}.jpg`;
}
