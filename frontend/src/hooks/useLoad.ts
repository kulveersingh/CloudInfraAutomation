import { useEffect, useRef, useState } from "react";

interface LoadSnapshot<T> {
  data?: T;
  error?: string;
  loading: boolean;
}

export interface LoadState<T> extends LoadSnapshot<T> {
  reload: () => void;
}

/** Runs an async loader on mount (and on reload) and exposes loading, data and error. */
export function useLoad<T>(load: () => Promise<T>): LoadState<T> {
  const [snapshot, setSnapshot] = useState<LoadSnapshot<T>>({ loading: true });
  const [version, setVersion] = useState(0);
  const loader = useRef(load);
  loader.current = load;

  useEffect(() => {
    let active = true;
    setSnapshot((previous) => ({ ...previous, loading: true }));
    loader.current().then(
      (data) => { if (active) setSnapshot({ data, loading: false }); },
      (error: Error) => { if (active) setSnapshot({ error: error.message, loading: false }); },
    );
    return () => { active = false; };
  }, [version]);

  return { ...snapshot, reload: () => setVersion((current) => current + 1) };
}
