import { afterEach } from 'vitest';

// Long synchronous sim tests run back to back only through microtasks, so the worker never reaches
// its I/O phase and the reporter's RPC calls time out on slower machines ("Timeout calling
// onTaskUpdate"). A macrotask yield after each test lets those replies through.
afterEach(() => new Promise<void>((resolve) => setImmediate(resolve)));
