import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Vitest запускается без globals, поэтому автоматический cleanup Testing Library
// не срабатывает — вызываем его явно.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// jsdom не реализует эти API, а MUI (scrollable Tabs) может к ним обращаться.
class ObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

globalThis.ResizeObserver ??= ObserverStub;
globalThis.IntersectionObserver ??= ObserverStub;
