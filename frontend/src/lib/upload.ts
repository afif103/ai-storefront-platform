/**
 * Presigned-URL upload helpers.
 *
 * Flow:
 *   1. POST /api/v1/tenants/me/media/upload-url  →  { media_id, upload_url, s3_key }
 *      (authenticated via apiFetch, which attaches Bearer token)
 *   2. PUT  file bytes to upload_url (direct to S3/MinIO)
 *      (NO auth headers — presigned URL signature would break)
 *
 * Uses XMLHttpRequest for the S3 PUT to track upload progress.
 */

import { apiFetch } from "@/lib/api-client";

// ------ Types ------

export interface UploadUrlResponse {
  media_id: string;
  upload_url: string;
  s3_key: string;
  expires_in: number;
}

export interface UploadResult {
  media_id: string;
  s3_key: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

// ------ Request presigned URL ------

interface RequestUploadUrlParams {
  file_name: string;
  content_type: string;
  size_bytes: number;
  entity_type?: string;
  entity_id?: string;
  product_id?: string;
}

export async function requestUploadUrl(
  params: RequestUploadUrlParams
): Promise<
  { ok: true; data: UploadUrlResponse } | { ok: false; detail: string }
> {
  const body: Record<string, unknown> = {
    file_name: params.file_name,
    content_type: params.content_type,
    size_bytes: params.size_bytes,
  };
  if (params.entity_type && params.entity_id) {
    body.entity_type = params.entity_type;
    body.entity_id = params.entity_id;
  }
  if (params.product_id) {
    body.product_id = params.product_id;
  }

  const result = await apiFetch<UploadUrlResponse>(
    "/api/v1/tenants/me/media/upload-url",
    { method: "POST", body: JSON.stringify(body) }
  );

  if (!result.ok) {
    return { ok: false, detail: result.detail };
  }
  return { ok: true, data: result.data };
}

// ------ PUT file to presigned URL with progress ------

export function uploadToPresignedUrl(
  uploadUrl: string,
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress({
          loaded: e.loaded,
          total: e.total,
          percent: Math.round((e.loaded / e.total) * 100),
        });
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Upload failed — network error"));
    });

    xhr.addEventListener("abort", () => {
      reject(new Error("Upload aborted"));
    });

    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.send(file);
  });
}

// ------ Convenience: full upload flow ------

export async function uploadFile(
  file: File,
  opts?: {
    entity_type?: string;
    entity_id?: string;
    product_id?: string;
    onProgress?: (progress: UploadProgress) => void;
  }
): Promise<{ ok: true; result: UploadResult } | { ok: false; detail: string }> {
  // 1. Get presigned URL
  const urlResult = await requestUploadUrl({
    file_name: file.name,
    content_type: file.type,
    size_bytes: file.size,
    entity_type: opts?.entity_type,
    entity_id: opts?.entity_id,
    product_id: opts?.product_id,
  });

  if (!urlResult.ok) {
    return { ok: false, detail: urlResult.detail };
  }

  // 2. PUT to S3
  try {
    await uploadToPresignedUrl(urlResult.data.upload_url, file, opts?.onProgress);
  } catch (err) {
    return {
      ok: false,
      detail: err instanceof Error ? err.message : "Upload failed",
    };
  }

  return {
    ok: true,
    result: {
      media_id: urlResult.data.media_id,
      s3_key: urlResult.data.s3_key,
    },
  };
}

// ------ Get download URL for a media asset ------

export async function getMediaDownloadUrl(
  mediaId: string
): Promise<{ ok: true; url: string } | { ok: false; detail: string }> {
  const result = await apiFetch<{ download_url: string }>(
    `/api/v1/tenants/me/media/${mediaId}/download-url`
  );
  if (!result.ok) {
    return { ok: false, detail: result.detail };
  }
  return { ok: true, url: result.data.download_url };
}
