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
