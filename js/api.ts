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

async function post(url: RequestInfo): Promise<Response> {
  const response = await fetch(url, {
    method: "POST",
    cache: "no-cache",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken()!,
    },
  });
  return response;
}

//

export async function actOnRelease(
  releaseId: string, action: string, isUndo: boolean,
): Promise<Response> {
  return post(`/releases/${releaseId}/${isUndo ? "un" : ""}${action}/`);
}

export async function pickTrack(
  trackId: string, isUnpick: boolean,
): Promise<Response> {
  return post(`/tracks/${trackId}/${isUnpick ? "un" : ""}pick/`);
}
