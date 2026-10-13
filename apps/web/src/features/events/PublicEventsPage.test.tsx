// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PublicEventsPage } from "./PublicEventsPage";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("browses anonymously and encodes search terms", async () => {
  const mock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(
      new Response(JSON.stringify({ items: [], totalPages: 0 })),
    );
  vi.stubGlobal("fetch", mock);
  render(
    <MemoryRouter>
      <PublicEventsPage />
    </MemoryRouter>,
  );
  await screen.findByText("No upcoming events found.");
  fireEvent.change(screen.getByLabelText("Search events"), {
    target: { value: "Seminar & workshop" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByText("No upcoming events found.");
  expect(mock.mock.calls[1][0]).toContain("keyword=Seminar%20%26%20workshop");
  expect(mock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
});
it("combines a real category filter with the search query", async () => {
  const mock = vi
    .fn<typeof fetch>()
    .mockImplementation(
      async () => new Response(JSON.stringify({ items: [], totalPages: 0 })),
    );
  vi.stubGlobal("fetch", mock);
  render(
    <MemoryRouter>
      <PublicEventsPage />
    </MemoryRouter>,
  );
  await screen.findByText("No upcoming events found.");
  fireEvent.click(screen.getByRole("combobox", { name: /Filter by category/ }));
  fireEvent.click(screen.getByRole("option", { name: "Technology" }));
  await screen.findByText("No upcoming events found.");
  expect(mock.mock.lastCall?.[0]).toContain("category=TECH");
});
