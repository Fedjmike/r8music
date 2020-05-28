export interface Track {
  id: string;
  title: string;
  runtime_str?: string;
}

export type Username = string;

//

function getCsrfToken(): string | undefined {
  const match = document.cookie.match(/csrftoken=([^;]*)/)
  return match?.[1];
}

async function post(url: RequestInfo, data?: {}): Promise<Response> {
  const response = await fetch(url, {
    method: "POST",
    cache: "no-cache",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken()!,
    },
    body: JSON.stringify(data),
  });
  return response;
}

//

function apiEndpoint(
  type: string, id: string, action: string, isUndo: boolean,
): string {
  return `/${type}/${id}/${isUndo ? "un" : ""}${action}/`;
}

export async function actOnRelease(
  releaseId: string, action: string, isUndo: boolean,
): Promise<Response> {
  return post(apiEndpoint("releases", releaseId, action, isUndo));
}

export async function rateRelease(
  releaseId: string, rating: number | null,
): Promise<Response> {
  const isUndo = rating == null;
  const endpoint = apiEndpoint("releases", releaseId, "rate", isUndo);
  return post(endpoint, { rating });
}

export async function pickTrack(
  trackId: string, isUnpick: boolean,
): Promise<Response> {
  return post(apiEndpoint("tracks", trackId, "pick", isUnpick));
}
