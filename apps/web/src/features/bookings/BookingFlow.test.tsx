// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { BookingForm } from "./BookingForm";
import { BookingDetail } from "./BookingsPage";
vi.mock("qrcode", () => ({
  default: {
    toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,test"),
  },
}));
const fetchMock = vi.fn<typeof fetch>();
const ticket = { id: "t1", credential: "unique-code", state: "VALID" };
const booking = {
  id: "b1",
  eventId: "e1",
  eventTitle: "Workshop",
  eventLocation: "Campus",
  startsAt: "2099-01-01T10:00:00Z",
  endsAt: "2099-01-01T12:00:00Z",
  ticketName: "General",
  status: "CONFIRMED",
  quantity: 1,
  amount: 0,
  tickets: [ticket],
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
beforeEach(() => {
  sessionStorage.clear();
  sessionStorage.setItem(
    "sems-auth",
    JSON.stringify({
      token: "test",
      user: { id: "u1", username: "Alice", roles: ["ATTENDEE"] },
    }),
  );
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function form() {
  return render(
    <AuthProvider>
      <MemoryRouter>
        <Routes>
          <Route
            path="/"
            element={
              <BookingForm
                eventId="e1"
                ticketTypeId="t1"
                available={10}
                opensAt="2020-01-01T00:00:00Z"
                closesAt="2099-01-01T00:00:00Z"
              />
            }
          />
          <Route path="/bookings/:id" element={<p>Booking confirmed</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}
it("preserves a request across an uncertain response and a page remount", async () => {
  fetchMock
    .mockRejectedValueOnce(new TypeError("Connection lost"))
    .mockResolvedValueOnce(response({ id: "b1" }));
  const mounted = form();
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm free booking" }));
  await screen.findByText("Connection lost");
  const first = JSON.parse(fetchMock.mock.calls[0][1]!.body as string);
  mounted.unmount();
  form();
  expect((screen.getByRole("spinbutton") as HTMLInputElement).disabled).toBe(
    true,
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry booking" }));
  await screen.findByText("Booking confirmed");
  expect(JSON.parse(fetchMock.mock.calls[1][1]!.body as string)).toEqual(first);
  expect(sessionStorage.getItem("sems-booking:u1:e1:t1")).toBeNull();
});
it("allows changing quantity after a definitive capacity rejection", async () => {
  fetchMock.mockResolvedValueOnce(
    response({ detail: "Not enough places" }, 409),
  );
  form();
  fireEvent.click(screen.getByRole("button", { name: "Confirm free booking" }));
  await screen.findByText("Not enough places");
  expect((screen.getByRole("spinbutton") as HTMLInputElement).disabled).toBe(
    false,
  );
});
it("requires cancellation confirmation and removes QR/manual codes afterwards", async () => {
  fetchMock
    .mockResolvedValueOnce(response(booking))
    .mockResolvedValueOnce(
      response({
        ...booking,
        status: "CANCELLED",
        tickets: [{ ...ticket, state: "CANCELLED" }],
      }),
    );
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/bookings/b1"]}>
        <Routes>
          <Route path="/bookings/:id" element={<BookingDetail />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
  await screen.findByAltText("Admission ticket QR code");
  expect(screen.getByText("unique-code")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancel booking" }));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
  await screen.findByText(/Booking cancelled/);
  expect(screen.queryByAltText("Admission ticket QR code")).toBeNull();
  expect(screen.queryByText("unique-code")).toBeNull();
});
