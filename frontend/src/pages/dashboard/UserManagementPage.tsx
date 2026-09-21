import React, { useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import { ApiResponse, User } from "../../types";
import { DashboardLayout } from "../../components/layout/DashboardLayout";
import { LoadingSpinner } from "../../components/common/LoadingSpinner";

export const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [updating, setUpdating] = useState("");
  useEffect(() => {
    setLoading(true);
    apiClient
      .get<ApiResponse<User[]>>(`/users?skip=${page * 100}&limit=100`)
      .then((r) => {
        setUsers(r.data.data);
        setError("");
      })
      .catch(() => setError("Unable to load accounts. Please try again."))
      .finally(() => setLoading(false));
  }, [page]);
  const toggle = async (user: User) => {
    setUpdating(user.id);
    try {
      const r = await apiClient.patch<ApiResponse<User>>(`/users/${user.id}`, {
        is_active: !user.is_active,
      });
      setUsers((all) => all.map((u) => (u.id === user.id ? r.data.data : u)));
      setError("");
    } catch {
      setError("Unable to update this account.");
    } finally {
      setUpdating("");
    }
  };
  return (
    <DashboardLayout>
      <div className="glass-card p-6 space-y-5">
        <h1 className="text-2xl font-bold">User Management</h1>
        <p className="text-slate-600">
          Review accounts and manage access to Spandan.
        </p>
        {error && (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        )}
        {loading ? (
          <LoadingSpinner />
        ) : (
          <div className="divide-y">
            {users.map((u) => (
              <div
                key={u.id}
                className="py-4 flex flex-wrap justify-between items-center gap-3"
              >
                <div>
                  <p className="font-semibold">{u.full_name || u.email}</p>
                  <p className="text-sm text-slate-600">
                    {u.email} · {u.role} · {u.is_active ? "Active" : "Inactive"}
                  </p>
                </div>
                {u.role !== "administrator" && (
                  <button
                    className="btn-secondary"
                    disabled={updating === u.id}
                    onClick={() => void toggle(u)}
                  >
                    {u.is_active ? "Deactivate" : "Activate"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-3">
          <button
            className="btn-secondary"
            disabled={page === 0 || loading}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <button
            className="btn-secondary"
            disabled={users.length < 100 || loading}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
};
