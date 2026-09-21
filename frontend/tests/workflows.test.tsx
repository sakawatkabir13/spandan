import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { apiClient } from "../src/api/client";
import { DoctorDiscoveryPage } from "../src/pages/doctors/DoctorDiscoveryPage";
import { AdminDashboard } from "../src/pages/dashboard/AdminDashboard";
import { ProfilePage } from "../src/pages/dashboard/ProfilePage";
import { LiveQueueConsolePage } from "../src/pages/dashboard/LiveQueueConsolePage";

const auth = vi.hoisted(() => ({
  user: {
    id: "user-1",
    full_name: "Dr. Test",
    email: "doctor@example.com",
    role: "doctor",
  },
  updateUser: vi.fn(),
}));
vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ ...auth, isAuthenticated: true }),
}));
vi.mock("../src/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));
vi.mock("../src/components/layout/DashboardLayout", () => ({
  DashboardLayout: ({ children }: any) => <div>{children}</div>,
}));
vi.mock("../src/components/layout/MainLayout", () => ({
  MainLayout: ({ children }: any) => <div>{children}</div>,
}));

const doctor = {
  id: "doc-1",
  full_name: "Dr. Test",
  medical_registration_number: "BMDC-123",
  verification_status: "approved",
  specializations: [{ id: "cardio", name: "Cardiology" }],
  qualifications: [{ id: "q1", title: "MBBS", institution: "Test College" }],
  years_of_experience: 10,
};
const response = (data: any) => ({ data: { success: true, data } });
beforeEach(() => {
  vi.clearAllMocks();
  auth.user.role = "doctor";
});
afterEach(cleanup);

describe("API-backed workflows", () => {
  it("renders the API doctor name, specialty and qualification", async () => {
    vi.mocked(apiClient.get).mockImplementation(
      async (url) =>
        response(
          url === "/doctors/specializations"
            ? doctor.specializations
            : [doctor],
        ) as any,
    );
    render(
      <MemoryRouter>
        <DoctorDiscoveryPage />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("link", { name: "Dr. Test" }),
    ).toBeInTheDocument();
    expect(screen.getByText("(MBBS)")).toBeInTheDocument();
    expect(screen.getAllByText("Cardiology").length).toBeGreaterThan(0);
  });

  it("loads a single doctor profile and saves specialties through the real schema", async () => {
    vi.mocked(apiClient.get).mockImplementation(
      async (url) =>
        response(
          url === "/doctors/me/profile"
            ? doctor
            : url === "/doctors/specializations"
              ? doctor.specializations
              : url === "/auth/me"
                ? auth.user
                : [],
        ) as any,
    );
    vi.mocked(apiClient.patch).mockResolvedValue(response(doctor) as any);
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    const name = await screen.findByDisplayValue("Dr. Test");
    fireEvent.change(name, { target: { value: "Dr. Updated" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Profile" }));
    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(
        "/doctors/me/profile",
        expect.objectContaining({
          full_name: "Dr. Updated",
          specialization_ids: ["cardio"],
        }),
      ),
    );
    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
  });

  it("reviews pending doctors and submits the verification status enum", async () => {
    auth.user.role = "administrator";
    vi.mocked(apiClient.get).mockResolvedValue(
      response([{ ...doctor, verification_status: "pending" }]) as any,
    );
    vi.mocked(apiClient.post).mockResolvedValue(response(doctor) as any);
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Approve BMDC" }),
    );
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        "/doctors/doc-1/verify",
        expect.objectContaining({ status: "approved" }),
      ),
    );
    expect(apiClient.get).toHaveBeenCalledWith("/doctors/admin/all");
  });

  it("shows serial zero before the queue starts and calls the queue endpoint", async () => {
    const schedule = {
      id: "s1",
      schedule_date: "2026-09-14",
      start_time: "17:00:00",
      end_time: "21:00:00",
      status: "open",
      maximum_patients: 5,
      queue_state: { current_serial: 0, delay_minutes: 0 },
    };
    vi.mocked(apiClient.get).mockImplementation(
      async (url) => response(url === "/schedules/s1" ? schedule : []) as any,
    );
    vi.mocked(apiClient.post).mockResolvedValue(response({}) as any);
    render(
      <MemoryRouter initialEntries={["/dashboard/doctor/queue?schedule_id=s1"]}>
        <LiveQueueConsolePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("#0")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Call Next Patient" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        "/schedules/s1/queue/increment",
      ),
    );
  });
});
