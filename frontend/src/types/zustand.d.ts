import 'zustand/middleware';

declare module 'zustand/middleware' {
  interface PersistOptions<T> {
    partialize?: (state: T) => Partial<T>;
  }
}

