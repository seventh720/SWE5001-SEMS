// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { ProfilePage } from "./ProfilePage";
const fetchMock = vi.fn<typeof fetch>();
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const user = { id: "u1", username: "original", email: "account@example.com", roles: ["ATTENDEE"] };
function mount() { render(<AuthProvider><MemoryRouter><ProfilePage /></MemoryRouter></AuthProvider>); }
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); sessionStorage.setItem("sems-auth", JSON.stringify({token:"token", user})); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });
it("saves a named contact without student ID and lists it for future use", async () => {
  fetchMock.mockResolvedValueOnce(response([])).mockResolvedValueOnce(response({id:"c1",label:"Family",realName:"Alex",version:0}));
  mount(); await screen.findByText(/No saved contacts yet/);
  fireEvent.click(screen.getByRole("button", {name:"Add contact"}));
  expect(screen.queryByLabelText("Student ID")).toBeNull();
  expect(screen.queryByText("Personal information · optional")).toBeNull();
  fireEvent.change(screen.getByLabelText("Contact label"), {target:{value:"Family"}});
  fireEvent.change(screen.getByLabelText("Full name"), {target:{value:"Alex"}});
  fireEvent.click(screen.getByRole("button", {name:"Save contact"}));
  await screen.findByRole("button", {name:"Edit Family"});
  expect(JSON.parse(fetchMock.mock.calls[1][1]!.body as string)).toMatchObject({label:"Family",realName:"Alex"});
  expect(JSON.parse(fetchMock.mock.calls[1][1]!.body as string)).not.toHaveProperty("studentId");
});
it("updates the session username after save and reports a duplicate without replacing it", async () => {
  fetchMock.mockResolvedValueOnce(response([])).mockResolvedValueOnce(response({...user,username:"new.name"})).mockResolvedValueOnce(response({detail:"Username is already registered"},409));
  mount(); await screen.findByText(/No saved contacts yet/);
  fireEvent.change(screen.getByLabelText("Username"), {target:{value:"new.name"}});
  fireEvent.click(screen.getByRole("button", {name:"Save username"}));
  await screen.findByText(/Username updated/);
  expect(JSON.parse(sessionStorage.getItem("sems-auth")!).user.username).toBe("new.name");
  fireEvent.change(screen.getByLabelText("Username"), {target:{value:"someone"}});
  fireEvent.click(screen.getByRole("button", {name:"Save username"}));
  await screen.findByRole("alert");
  expect(JSON.parse(sessionStorage.getItem("sems-auth")!).user.username).toBe("new.name");
});
it("deletes only the selected version after confirmation", async () => {
  fetchMock.mockResolvedValueOnce(response([{id:"c1",label:"Family",version:2},{id:"c2",label:"Work",version:0}])).mockResolvedValueOnce(new Response(null,{status:204}));
  mount(); fireEvent.click(await screen.findByRole("button", {name:"Edit Family"}));
  fireEvent.click(screen.getByRole("button", {name:"Delete contact"}));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", {name:"Confirm delete"}));
  await screen.findByText(/Contact deleted/);
  expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/profile/contacts/c1?version=2");
  expect(screen.getByRole("button", {name:"Edit Work"})).toBeTruthy();
});
