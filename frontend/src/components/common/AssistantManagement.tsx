import React, { useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import { ApiResponse } from "../../types";

interface Assignment {
  id: string;
  is_active: boolean;
  can_manage_schedules: boolean;
  can_manage_appointments: boolean;
  can_update_queue: boolean;
  assistant: { email: string };
}

export const AssistantManagement: React.FC<{ doctorId: string }> = ({
  doctorId,
}) => {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    apiClient
      .get<ApiResponse<Assignment[]>>("/assistants")
      .then((r) => setAssignments(r.data.data))
      .catch(() => setMessage("Unable to load assistants."));
  useEffect(() => {
    void load();
  }, []);
  const create = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setBusy(true);
    try {
      await apiClient.post("/auth/register/assistant", {
        ...data,
        doctor_id: doctorId,
      });
      form.reset();
      setMessage(
        "Assistant created. Give the assistant their sign-in details.",
      );
      await load();
    } catch (error: any) {
      setMessage(
        error.response?.data?.error?.message || "Unable to create assistant.",
      );
    } finally {
      setBusy(false);
    }
  };
  const update = async (
    assignment: Assignment,
    key: keyof Omit<Assignment, "id" | "assistant">,
  ) => {
    setBusy(true);
    try {
      await apiClient.patch(`/assistants/${assignment.id}`, {
        ...assignment,
        [key]: !assignment[key],
      });
      await load();
    } catch {
      setMessage("Unable to update assistant permissions.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="glass-card p-6 space-y-4">
      <h2 className="text-xl font-bold">Chamber Assistants</h2>
      {message && (
        <p role="status" className="text-sm text-spandan-800">
          {message}
        </p>
      )}
      <form onSubmit={create} className="grid sm:grid-cols-2 gap-3">
        <label className="text-sm">
          Full name
          <input
            name="full_name"
            required
            minLength={2}
            className="input-field"
          />
        </label>
        <label className="text-sm">
          Email
          <input name="email" type="email" required className="input-field" />
        </label>
        <label className="text-sm">
          Phone
          <input
            name="phone_number"
            type="tel"
            required
            className="input-field"
          />
        </label>
        <label className="text-sm">
          Initial password
          <input
            name="password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            className="input-field"
          />
        </label>
        <button disabled={busy} className="btn-primary sm:col-span-2">
          Create Assistant
        </button>
      </form>
      {assignments.map((a) => (
        <div key={a.id} className="border-t pt-4 space-y-2">
          <p className="font-semibold">{a.assistant.email}</p>
          <div className="flex flex-wrap gap-4">
            {(
              [
                ["is_active", "Active"],
                ["can_manage_schedules", "Schedules"],
                ["can_manage_appointments", "Appointments"],
                ["can_update_queue", "Queue"],
              ] as const
            ).map(([key, title]) => (
              <label key={key} className="text-sm flex items-center gap-2">
                <input
                  type="checkbox"
                  disabled={busy}
                  checked={a[key]}
                  onChange={() => void update(a, key)}
                />
                {title}
              </label>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
};
