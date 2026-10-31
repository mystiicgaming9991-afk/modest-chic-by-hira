import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CustomersPage from "./page";

const { staffJson, replace } = vi.hoisted(() => ({
  staffJson: vi.fn(),
  replace: vi.fn(),
}));

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

const profile = {
  id: "11111111-1111-4111-8111-111111111111",
  normalized_phone: "+923001234567",
  display_phone: "03001234567",
  name: "Ayesha Khan",
  email: "ayesha@example.test",
  account_status: "ACTIVE" as const,
  account_email: "ayesha@example.test",
  account_updated_at: "2026-10-25T10:00:00+00:00",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe("customer account administration", () => {
  beforeEach(() => {
    staffJson.mockReset();
    replace.mockReset();
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") {
        return { id: "staff", email: "staff@example.test", name: "Staff", permission_keys: ["customer.read", "customer.manage"], totp_enabled: true };
      }
      if (path.startsWith("admin/customers?q=")) return [profile];
      if (path.endsWith("/consents/marketing-email")) return { consented: false, source: "customer_self_service", recorded_at: "2026-10-25T10:00:00+00:00", policy_version_id: null };
      if (path.endsWith("/orders")) return [];
      if (path.endsWith("/addresses")) {
        return init?.method === "POST"
          ? { id: "address-1", ...JSON.parse(String(init.body)) }
          : [];
      }
      if (path.endsWith("/account-status")) {
        return { customer_id: profile.id, status: "SUSPENDED", updated_at: "2026-10-25T10:01:00+00:00" };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
  });

  it("lets permitted staff suspend an account using its loaded version", async () => {
    const user = userEvent.setup();
    render(<CustomersPage />);
    expect(await screen.findByRole("heading", { name: "Customer profiles" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));
    await user.click(await screen.findByRole("button", { name: "Suspend account" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Re-activate account" })).toBeInTheDocument());
    const [path, init] = staffJson.mock.calls.find(([requestPath]) => requestPath.endsWith("/account-status")) ?? [];
    expect(path).toBe(`admin/customers/${profile.id}/account-status`);
    expect(JSON.parse(init.body as string)).toEqual({
      status: "SUSPENDED",
      expected_updated_at: profile.account_updated_at,
    });
  });

  it("lets customer managers add a reusable address through the staff API", async () => {
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));

    await user.type(await screen.findByLabelText("Recipient name"), "Ayesha Khan");
    await user.type(screen.getByLabelText("Recipient phone"), "03001234567");
    await user.type(screen.getByLabelText("Address line 1"), "12 Example Road");
    await user.type(screen.getByLabelText("Area"), "Gulberg");
    await user.type(screen.getByLabelText("City"), "Karachi");
    await user.type(screen.getByLabelText("Delivery notes"), "Call on arrival");
    await user.click(screen.getByLabelText("Set as default address"));
    await user.click(screen.getByRole("button", { name: "Save address" }));

    expect(await screen.findByText(/12 Example Road, Gulberg, Karachi, PK/)).toBeInTheDocument();
    expect(screen.getByText(/03001234567 · Call on arrival/)).toBeInTheDocument();
    const [path, init] = staffJson.mock.calls.find(([requestPath, request]) => requestPath.endsWith("/addresses") && request?.method === "POST") ?? [];
    expect(path).toBe(`admin/customers/${profile.id}/addresses`);
    expect(JSON.parse(init.body as string)).toMatchObject({
      recipient_name: "Ayesha Khan",
      phone: "03001234567",
      line1: "12 Example Road",
      area: "Gulberg",
      city: "Karachi",
      delivery_notes: "Call on arrival",
      is_default: true,
    });
  });

  it("moves the default-address indicator when a new default is saved", async () => {
    const existingAddress = {
      id: "address-existing", recipient_name: "Ayesha Khan", phone: null, line1: "Old Street",
      line2: null, area: null, city: "Karachi", postal_code: null, delivery_notes: null,
      country_code: "PK", is_default: true, updated_at: "2026-10-25T10:00:00+00:00",
    };
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return { id: "staff", email: "staff@example.test", name: "Staff", permission_keys: ["customer.read", "customer.manage"], totp_enabled: true };
      if (path.startsWith("admin/customers?q=")) return [profile];
      if (path.endsWith("/orders")) return [];
      if (path.endsWith("/consents/marketing-email")) return null;
      if (path.endsWith("/addresses")) return init?.method === "POST"
        ? { id: "address-new", ...JSON.parse(String(init.body)) }
        : [existingAddress];
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));
    expect(await screen.findByText(/Old Street, Karachi, PK/)).toBeInTheDocument();
    expect(screen.getAllByText("Default")).toHaveLength(1);

    await user.type(screen.getByLabelText("Address line 1"), "New Street");
    await user.type(screen.getByLabelText("City"), "Lahore");
    await user.click(screen.getByLabelText("Set as default address"));
    await user.click(screen.getByRole("button", { name: "Save address" }));

    expect(await screen.findByText(/New Street, Lahore, PK/)).toBeInTheDocument();
    expect(screen.getAllByText("Default")).toHaveLength(1);
    expect(screen.getByText(/Old Street, Karachi, PK/)).toBeInTheDocument();
  });

  it("edits a saved address with the version it was loaded with", async () => {
    const existingAddress = {
      id: "address-existing", recipient_name: "Ayesha Khan", phone: "03001234567", line1: "Old Street",
      line2: null, area: "Gulberg", city: "Karachi", postal_code: null, delivery_notes: null,
      country_code: "PK", is_default: false, updated_at: "2026-10-25T10:00:00+00:00",
    };
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return { id: "staff", email: "staff@example.test", name: "Staff", permission_keys: ["customer.read", "customer.manage"], totp_enabled: true };
      if (path.startsWith("admin/customers?q=")) return [profile];
      if (path.endsWith("/orders")) return [];
      if (path.endsWith("/consents/marketing-email")) return null;
      if (path.endsWith("/addresses")) return [existingAddress];
      if (path.endsWith(`/addresses/${existingAddress.id}`) && init?.method === "PATCH") {
        return { ...existingAddress, ...JSON.parse(String(init.body)), updated_at: "2026-10-25T10:05:00+00:00" };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));
    await user.click(await screen.findByRole("button", { name: "Edit address" }));
    const line1 = screen.getByLabelText("Address line 1");
    await user.clear(line1);
    await user.type(line1, "Updated Street");
    await user.click(screen.getByRole("button", { name: "Update address" }));

    expect(await screen.findByText(/Updated Street, Gulberg, Karachi, PK/)).toBeInTheDocument();
    const [path, init] = staffJson.mock.calls.find(([requestPath, request]) => requestPath.endsWith(`/addresses/${existingAddress.id}`) && request?.method === "PATCH") ?? [];
    expect(path).toBe(`admin/customers/${profile.id}/addresses/${existingAddress.id}`);
    expect(JSON.parse(init.body as string)).toMatchObject({
      expected_updated_at: existingAddress.updated_at,
      line1: "Updated Street",
      city: "Karachi",
      is_default: false,
    });
  });

  it("uses the new version when editing an address whose default status just changed", async () => {
    const existingAddress = {
      id: "address-existing", recipient_name: "Ayesha Khan", phone: null, line1: "Old Street",
      line2: null, area: null, city: "Karachi", postal_code: null, delivery_notes: null,
      country_code: "PK", is_default: true, updated_at: "2026-10-25T10:00:00+00:00",
    };
    const newlyDefaultedAt = "2026-10-25T10:01:00+00:00";
    staffJson.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "auth/me") return { id: "staff", email: "staff@example.test", name: "Staff", permission_keys: ["customer.read", "customer.manage"], totp_enabled: true };
      if (path.startsWith("admin/customers?q=")) return [profile];
      if (path.endsWith("/orders")) return [];
      if (path.endsWith("/consents/marketing-email")) return null;
      if (path.endsWith("/addresses") && init?.method === "POST") {
        return {
          id: "address-new", ...JSON.parse(String(init.body)),
          default_address_updates: [{ id: existingAddress.id, updated_at: newlyDefaultedAt }],
          updated_at: "2026-10-25T10:01:00+00:00",
        };
      }
      if (path.endsWith("/addresses")) return [existingAddress];
      if (path.endsWith(`/addresses/${existingAddress.id}`) && init?.method === "PATCH") {
        return { ...existingAddress, ...JSON.parse(String(init.body)) };
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));
    await user.type(await screen.findByLabelText("Address line 1"), "New Street");
    await user.type(screen.getByLabelText("City"), "Lahore");
    await user.click(screen.getByLabelText("Set as default address"));
    await user.click(screen.getByRole("button", { name: "Save address" }));
    await screen.findByText(/New Street, Lahore, PK/);
    await user.click(screen.getAllByRole("button", { name: "Edit address" })[1]);
    await user.click(screen.getByRole("button", { name: "Update address" }));

    const [path, init] = staffJson.mock.calls.find(([requestPath, request]) => requestPath.endsWith(`/addresses/${existingAddress.id}`) && request?.method === "PATCH") ?? [];
    expect(path).toBe(`admin/customers/${profile.id}/addresses/${existingAddress.id}`);
    expect(JSON.parse(init.body as string).expected_updated_at).toBe(newlyDefaultedAt);
  });

  it("shows the latest marketing email decision without offering a send action", async () => {
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));

    expect(await screen.findByText(/Opted out · customer self service/)).toBeInTheDocument();
    expect(screen.getByText(/marketing sends remain disabled/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send marketing/i })).not.toBeInTheDocument();
    expect(staffJson).toHaveBeenCalledWith(`admin/customers/${profile.id}/consents/marketing-email`);
  });

  it("hides address editing from staff without customer management permission", async () => {
    staffJson.mockImplementation(async (path: string) => {
      if (path === "auth/me") return { id: "staff", email: "staff@example.test", name: "Reader", permission_keys: ["customer.read"], totp_enabled: true };
      if (path.startsWith("admin/customers?q=")) return [profile];
      if (path.endsWith("/consents/marketing-email")) return null;
      if (path.endsWith("/orders") || path.endsWith("/addresses")) return [];
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));

    expect(await screen.findByText("No saved addresses.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add a saved address" })).not.toBeInTheDocument();
  });

  it("ignores an older profile response after staff select a different customer", async () => {
    const secondProfile = { ...profile, id: "22222222-2222-4222-8222-222222222222", name: "Sana Ahmed" };
    const firstOrders = deferred<unknown>();
    const firstAddresses = deferred<unknown>();
    const firstConsent = deferred<unknown>();
    const secondOrders = deferred<unknown>();
    const secondAddresses = deferred<unknown>();
    const secondConsent = deferred<unknown>();
    staffJson.mockImplementation((path: string) => {
      if (path === "auth/me") return Promise.resolve({ id: "staff", email: "staff@example.test", name: "Staff", permission_keys: ["customer.read"], totp_enabled: true });
      if (path.startsWith("admin/customers?q=")) return Promise.resolve([profile, secondProfile]);
      const second = path.includes(secondProfile.id);
      if (path.endsWith("/orders")) return second ? secondOrders.promise : firstOrders.promise;
      if (path.endsWith("/addresses")) return second ? secondAddresses.promise : firstAddresses.promise;
      if (path.endsWith("/consents/marketing-email")) return second ? secondConsent.promise : firstConsent.promise;
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    render(<CustomersPage />);
    await user.type(await screen.findByLabelText("Name, email, or phone"), "Ayesha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Ayesha Khan/ }));
    await user.click(await screen.findByRole("button", { name: /Sana Ahmed/ }));

    secondOrders.resolve([]);
    secondAddresses.resolve([{
      id: "second-address", recipient_name: "Sana Ahmed", phone: null, line1: "Second Street",
      line2: null, area: null, city: "Lahore", postal_code: null, delivery_notes: null,
      country_code: "PK", is_default: true,
    }]);
    secondConsent.resolve({ consented: true, source: "customer_self_service", recorded_at: "2026-10-25T10:00:00+00:00", policy_version_id: null });
    expect(await screen.findByText(/Second Street, Lahore, PK/)).toBeInTheDocument();
    expect(screen.getByText(/Consent recorded · customer self service/)).toBeInTheDocument();

    firstOrders.resolve([]);
    firstAddresses.resolve([{
      id: "first-address", recipient_name: "Ayesha Khan", phone: null, line1: "First Street",
      line2: null, area: null, city: "Karachi", postal_code: null, delivery_notes: null,
      country_code: "PK", is_default: true,
    }]);
    firstConsent.resolve({ consented: false, source: "customer_self_service", recorded_at: "2026-10-25T10:00:00+00:00", policy_version_id: null });

    await waitFor(() => {
      expect(screen.getByText(/Second Street, Lahore, PK/)).toBeInTheDocument();
      expect(screen.queryByText(/First Street, Karachi, PK/)).not.toBeInTheDocument();
      expect(screen.getByText(/Consent recorded · customer self service/)).toBeInTheDocument();
    });
  });
});
