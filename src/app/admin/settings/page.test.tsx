import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StoreSettingsPage from "./page";

const { staffJson, replace } = vi.hoisted(() => ({ staffJson: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/staff-client", () => ({
  staffJson,
  jsonBody: (value: object) => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  }),
}));

const owner = {
  id: "owner-1",
  email: "owner@example.test",
  name: "Owner",
  totp_enabled: true,
  permission_keys: ["settings.manage"],
};

const settings = [
  {
    key: "fulfillment.availability",
    value: { cities: ["Karachi"] },
    is_secret: false,
    version: 1,
    updated_at: "2026-10-25T10:00:00Z",
    updated_by: null,
  },
  {
    key: "checkout.guest_allowed",
    value: false,
    is_secret: false,
    version: 2,
    updated_at: "2026-10-25T10:00:00Z",
    updated_by: null,
  },
  {
    key: "provider.resend_api_key",
    value: "***",
    is_secret: true,
    version: 1,
    updated_at: "2026-10-25T10:00:00Z",
    updated_by: null,
  },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("store settings and policy workspace", () => {
  beforeEach(() => {
    replace.mockReset();
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return owner;
      if (path === "admin/settings") return { items: settings };
      if (path.startsWith("admin/policies?type=")) return { items: [] };
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("requires settings.manage before loading private configuration", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return { ...owner, permission_keys: ["dashboard.read"] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<StoreSettingsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Store settings are restricted");
    expect(staffJson).toHaveBeenCalledTimes(1);
  });

  it("loads settings once and saves a selected value with its current version", async () => {
    const user = userEvent.setup();
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return owner;
      if (path === "admin/settings" && init?.method === "PUT") {
        return { ...settings[1], value: true, version: 3 };
      }
      if (path === "admin/settings") return { items: settings };
      if (path.startsWith("admin/policies?type=")) return { items: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<StoreSettingsPage />);
    await screen.findByText(/Current version 1/);
    await user.click(screen.getByRole("button", { name: /Guest checkout/ }));

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).not.toBeChecked();
    expect(staffJson.mock.calls.filter(([path]) => path === "admin/settings")).toHaveLength(1);

    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Save setting" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("saved as version 3"));
    expect(staffJson).toHaveBeenCalledWith("admin/settings", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ key: "checkout.guest_allowed", value: true, version: 2 }),
    }));
  });

  it("keeps secret values masked and does not prefill the secret editor", async () => {
    const user = userEvent.setup();
    render(<StoreSettingsPage />);
    await screen.findByText(/Current version 1/);
    await user.click(screen.getByRole("button", { name: /Resend API key/ }));

    const input = screen.getByLabelText("New secret");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveValue("");
    expect(screen.getByText("Saved secret: masked. Leaving this field blank keeps the current value.")).toBeInTheDocument();
    expect(screen.queryByText("***")).not.toBeInTheDocument();
  });

  it("locks settings and policy controls while a write is in flight", async () => {
    const user = userEvent.setup();
    const save = deferred<(typeof settings)[number]>();
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return owner;
      if (path === "admin/settings" && init?.method === "PUT") return save.promise;
      if (path === "admin/settings") return { items: settings };
      if (path.startsWith("admin/policies?type=")) return { items: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<StoreSettingsPage />);
    await screen.findByText(/Current version 1/);
    await user.click(screen.getByRole("button", { name: "Save setting" }));

    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/settings", expect.objectContaining({ method: "PUT" })));
    expect(screen.getByLabelText("JSON value")).toBeDisabled();
    expect(screen.getByRole("button", { name: /Guest checkout/ })).toBeDisabled();
    expect(screen.getByLabelText("Policy type")).toBeDisabled();

    save.resolve(settings[0]);
    expect(await screen.findByRole("status")).toHaveTextContent("saved as version 1");
  });

  it("ignores a late response from the previously selected policy type", async () => {
    const user = userEvent.setup();
    const shipping = deferred<{ items: Array<{ id: string; type: string; version: number; effective_from: string; content: Record<string, unknown>; approved_by: string | null; created_at: string }> }>();
    const returns = deferred<{ items: Array<{ id: string; type: string; version: number; effective_from: string; content: Record<string, unknown>; approved_by: string | null; created_at: string }> }>();
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return owner;
      if (path === "admin/settings") return { items: [] };
      if (path === "admin/policies?type=shipping") return shipping.promise;
      if (path === "admin/policies?type=returns") return returns.promise;
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<StoreSettingsPage />);
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/policies?type=shipping"));
    await user.selectOptions(await screen.findByLabelText("Policy type"), "returns");
    await waitFor(() => expect(staffJson).toHaveBeenCalledWith("admin/policies?type=returns"));

    returns.resolve({ items: [{ id: "returns-v2", type: "returns", version: 2, effective_from: "2026-10-25T00:00:00Z", content: {}, approved_by: null, created_at: "2026-10-25T00:00:00Z" }] });
    expect(await screen.findByText("Version 2")).toBeInTheDocument();
    shipping.resolve({ items: [{ id: "shipping-v1", type: "shipping", version: 1, effective_from: "2026-10-24T00:00:00Z", content: {}, approved_by: null, created_at: "2026-10-24T00:00:00Z" }] });

    await waitFor(() => expect(screen.getByText("Version 2")).toBeInTheDocument());
    expect(screen.queryByText("Version 1")).not.toBeInTheDocument();
  });
});
