interface SetType<T, AR, DR> {
  has(v: T): boolean;
  add(v: T): AR;
  delete(v: T): DR;
}

export function toggleSet<S extends SetType<T, AR, DR>, T, AR, DR>(
  set: S,
  value: T
): AR | DR {
  return set.has(value) ? set.delete(value) : set.add(value);
}

// Sets state to the given success state before the promise completes, but
// reverts the state if the eventual response isn't an 'okay' HTTP status code.
// For the purpose of a responsive-feeling UI.
export async function setOnSuccessEagerly<T>(
  promise: Promise<Response>,
  originalState: T,
  setState: (state: T) => void,
  successState: T,
): Promise<void>;
export async function setOnSuccessEagerly<T, K extends keyof T>(
  promise: Promise<Response>,
  originalState: T,
  setState: (state: Pick<T, K>) => void,
  successState: Pick<T, K>,
): Promise<void>;

export async function setOnSuccessEagerly<T>(
  promise: Promise<Response>,
  originalState: T,
  setState: (state: T) => void,
  successState: T,
): Promise<void> {
  setState(successState);
  const response = await promise;

  if (!response.ok) {
    setState(originalState);
  }
}
